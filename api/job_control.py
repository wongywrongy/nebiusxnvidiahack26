"""One controller owns job allowances, worker claims, accounting and publication."""

import base64
import hashlib
import hmac
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .config import settings
from .pipeline.cases import all_cases
from .providers import budget, campaign
from .readiness import manifest, invalid_reasons
from .schemas import Result

MAX_REPORT_BYTES = 16 * 1024 * 1024
ARCHIVE_PATH = re.compile(r"([A-Za-z0-9_-]+)/[0-9TZ+_-]+/([0-9a-f]{64})\.(txt|pdf)")


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session: str = Field(pattern=r"^[0-9a-f]{32}$")


class WorkerReport(Claim):
    run_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,160}$")
    checked_at: str
    manifest: dict
    wallet: campaign.State
    results: dict[str, Result]
    artifacts: dict[str, str] = {}
    duration_ms: int = Field(ge=0)
    failure: str | None = None


def signature(lease_id: str, action: str, body: bytes) -> str:
    return hmac.new(settings.secret("worker_token").encode(),
                    f"{lease_id}:{action}:".encode() + body, hashlib.sha256).hexdigest()


def authenticate(lease_id: str, action: str, body: bytes, supplied: str) -> None:
    if (not re.fullmatch(r"[0-9a-f]{32}", lease_id) or not settings.secret("worker_token")
            or not re.fullmatch(r"[0-9a-f]{64}", supplied)
            or not hmac.compare_digest(signature(lease_id, action, body), supplied)):
        raise HTTPException(403, "Worker lease authentication failed")


def configured() -> bool:
    return bool(settings.controller_state_dir and settings.secret("worker_token"))


def controller_origin(value: str) -> bool:
    try:
        url = urlsplit(value)
        return bool(url.scheme == "https" and url.hostname and url.username is None and url.password is None
                    and not url.query and not url.fragment and url.path in ("", "/")
                    and not any(char.isspace() for char in value) and (url.port is None or url.port > 0))
    except ValueError:
        return False


def public(job: campaign.JobLease) -> dict:
    return job.model_dump(include={"name", "id", "created_at", "state", "raw_state", "state_known", "poll_error",
                                   "failure", "duration_ms", "run_id", "report_at"})


def records() -> list[campaign.JobLease]:
    if not settings.controller_state_dir:
        return []
    with campaign.transaction(settings.campaign_budget_file) as state:
        return sorted(state.jobs.values(), key=lambda job: job.created_at, reverse=True)


def latest() -> dict | None:
    with campaign.transaction(settings.campaign_budget_file) as state:
        return state.watch_report


def reserve(request_id: str) -> tuple[campaign.JobLease, bool]:
    if not configured():
        raise HTTPException(409, "Cloud jobs require an imported controller authority and worker credential")
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", settings.speccheck_image):
        raise HTTPException(409, "Cloud jobs require an immutable image digest")
    if any(path == str(settings.campaign_budget_file.resolve()) for path, _ in campaign.FAILED_SETTLEMENTS):
        raise budget.BudgetExceeded("Failed campaign settlement requires reconciliation")
    ids = sorted(key for key, case in all_cases().items() if case.get("watch"))
    if not ids:
        raise HTTPException(409, "No bundled items are watched")
    now = datetime.now(timezone.utc)
    with campaign.transaction(settings.campaign_budget_file) as state:
        if existing := next((job for job in state.jobs.values() if job.request_id == request_id), None):
            return existing, False
        if any(not job.settled for job in state.jobs.values()):
            raise HTTPException(409, "A cloud job still has an unsettled allowance")
        if state.jobs and (now - max(datetime.fromisoformat(job.created_at) for job in state.jobs.values())).total_seconds() < settings.watch_run_interval_s:
            raise HTTPException(429, "A cloud job was requested recently; wait for the rate-limit interval")
        allowance = campaign.Amount(usd_nano=budget.usd_nano(settings.budget_usd_per_run),
            credits=min(math.floor(settings.budget_tavily_credits_per_day), len(ids) * math.floor(settings.budget_tavily_credits_per_item)))
        if not allowance.usd_nano or not allowance.credits:
            raise budget.BudgetExceeded("Cloud jobs require a positive bounded allowance")
        name = f"speccheck-recheck-{now.strftime('%Y%m%d-%H%M%S-%f')}"
        payment = campaign._reserve(state, allowance, run=name, item="job-allowance",
            run_usd_nano=allowance.usd_nano, day_usd_nano=budget.usd_nano(settings.budget_usd_per_day),
            item_credits=allowance.credits, day_credits=math.floor(settings.budget_tavily_credits_per_day), scopes=[])
        state.payments[payment].kind = "job"
        profile = manifest()
        profile["config"]["budget_usd_per_day"] = allowance.usd_nano / 1e9
        profile["config"]["budget_tavily_credits_per_day"] = allowance.credits
        profile["config_hash"] = hashlib.sha256(json.dumps(profile["config"], sort_keys=True).encode()).hexdigest()
        lease_id = uuid.uuid4().hex
        job = campaign.JobLease(lease_id=lease_id, request_id=request_id, name=name, created_at=now.isoformat(),
            payment_id=payment, phase=state.phase, allowance=allowance, ids=ids, image=settings.speccheck_image, manifest=profile)
        state.jobs[lease_id] = job
        return job, True


def claimed(lease_id: str, claim: Claim) -> dict:
    with campaign.transaction(settings.campaign_budget_file) as state:
        job = state.jobs.get(lease_id)
        if not job or job.settled or job.report_hash or state.retired_to:
            raise HTTPException(409, "This worker lease is not available")
        if job.worker_session and job.worker_session != claim.session:
            raise HTTPException(409, "This allowance was already claimed by another worker process")
        if datetime.now(timezone.utc) > datetime.fromisoformat(job.created_at) + timedelta(hours=2):
            raise HTTPException(409, "Worker lease expired; its allowance is retained for reconciliation")
        if state.blocked:
            raise budget.BudgetExceeded("Controller accounting requires reconciliation before claiming paid work")
        job.worker_session = claim.session
        return {"lease_id": lease_id, "job_name": job.name, "ids": job.ids, "manifest": job.manifest,
                "allowance": job.allowance.model_dump()}


def _validate_report(job: campaign.JobLease, report: WorkerReport) -> tuple[dict, bool]:
    from scripts.recheck import summarize

    if report.session != job.worker_session or report.manifest != job.manifest:
        raise HTTPException(409, "Worker session or immutable configuration does not match its lease")
    wallet = report.wallet
    campaign._validate(wallet)
    if (not wallet.blocked or wallet.seed != campaign.Amount() or wallet.day_seed or wallet.jobs or wallet.retired_to
            or wallet.limit != job.allowance or wallet.phase != "engineering"
            or wallet.phases != {"engineering": job.allowance, "final": campaign.Amount()}
            or set(report.results) - set(job.ids)
            or any(payment.item not in job.ids or payment.run != report.run_id or payment.kind != "request"
                   for payment in wallet.payments.values())):
        raise HTTPException(409, "Worker wallet was not sealed within its assigned allowance")
    try:
        stamp = datetime.fromisoformat(report.checked_at)
    except ValueError:
        raise HTTPException(409, "Worker report time is invalid") from None
    if (stamp.tzinfo is None or stamp < datetime.fromisoformat(job.created_at)
            or stamp > datetime.now(timezone.utc) + timedelta(minutes=5)
            or any(not job.created_at[:10] <= payment.day <= stamp.date().isoformat() for payment in wallet.payments.values())):
        raise HTTPException(409, "Worker report time does not belong to this lease")
    cases = all_cases()
    valid = set(report.results) == set(job.ids) and report.failure is None
    for key, result in report.results.items():
        usage = [payment.actual for payment in wallet.payments.values() if payment.item == key and payment.actual is not None]
        actual = campaign._sum(usage)
        if (result.case_id != key or result.mode != "live" or not result.findings or invalid_reasons(result)
                or result.config_hash != job.manifest["config_hash"]
                or budget.usd_nano(result.fresh_model_cost_usd) != actual.usd_nano or result.fresh_web_credits != actual.credits):
            valid = False
        if any(not finding.evidence for finding in result.findings if finding.check in ("currency", "status")
               and finding.verdict in ("pass", "fail", "outdated")):
            valid = False
        if any(not evidence.archived_path for finding in result.findings if finding.check in ("currency", "status")
               and finding.verdict in ("pass", "fail", "outdated") for evidence in finding.evidence):
            valid = False
    items = [summarize(cases[key], report.results.get(key)) for key in job.ids]
    valid &= all(item["status"] != "unverified" for item in items)
    return {"checked_at": report.checked_at, "runner": "Nebius Serverless Job", "mode": "live",
            "job_name": job.name, "run_id": report.run_id, "duration_ms": report.duration_ms,
            "models": job.manifest["config"]["models"], "items": items}, valid


def _artifacts(job: campaign.JobLease, report: WorkerReport) -> dict[str, bytes]:
    files = {}
    for relative, encoded in report.artifacts.items():
        match = ARCHIVE_PATH.fullmatch(relative)
        if not match or match[1] not in job.ids:
            raise HTTPException(409, "Worker evidence path does not belong to its lease")
        try:
            content = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise HTTPException(409, "Worker evidence encoding is invalid") from None
        if hashlib.sha256(content).hexdigest() != match[2] or match[3] == "pdf" and not content.startswith(b"%PDF"):
            raise HTTPException(409, "Worker evidence does not match its content hash")
        files[relative] = content
    if sum(map(len, files.values())) > MAX_REPORT_BYTES:
        raise HTTPException(413, "Worker evidence exceeds the report limit")
    def references(value):
        if isinstance(value, dict):
            if value.get("archived_path"):
                yield value["archived_path"]
            yield from value.get("archived_submittals", [])
            for child in value.values():
                yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)
    if set(references({key: result.model_dump() for key, result in report.results.items()})) - files.keys():
        raise HTTPException(409, "Worker report is missing its referenced evidence files")
    return files


def _finalize(state: campaign.State, job: campaign.JobLease) -> None:
    if job.settled or not job.cloud_terminal or job.report_path is None:
        return
    stored = (settings.controller_state_dir / job.report_path).read_bytes()
    if hashlib.sha256(stored).hexdigest() != job.report_digest:
        raise budget.BudgetExceeded("Worker receipt is corrupt; allowance retained")
    report = WorkerReport.model_validate_json(stored)
    published, valid = _validate_report(job, report)
    files = _artifacts(job, report)
    if files and settings.evidence_dir is None:
        raise budget.BudgetExceeded("Controller evidence archive is unavailable; allowance retained")
    for relative, content in files.items():
        target = (settings.evidence_dir / relative).resolve()
        if not target.is_relative_to(settings.evidence_dir.resolve()):
            raise budget.BudgetExceeded("Controller evidence archive path is invalid")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != content:
            raise budget.BudgetExceeded("Controller evidence hash path is corrupt; allowance retained")
        target.write_bytes(content)
    actual = campaign._sum([p.actual for p in report.wallet.payments.values() if p.actual is not None])
    for key, payment in report.wallet.payments.items():
        if payment.actual is not None:
            identifier = f"job:{job.lease_id}:{key}"
            entry = payment.model_copy(update={"run": job.name, "phase": job.phase, "owner": f"job:{job.lease_id}", "scopes": []})
            if identifier in state.payments and state.payments[identifier] != entry:
                raise budget.BudgetExceeded("Conflicting worker accounting; allowance retained")
            state.payments[identifier] = entry
    escrow = state.payments[job.payment_id]
    escrow.held = campaign.Amount(usd_nano=max(0, job.allowance.usd_nano - actual.usd_nano),
                                 credits=max(0, job.allowance.credits - actual.credits))
    unknown = any(p.actual is None or p.unknown for p in report.wallet.payments.values())
    exceeded = (actual.usd_nano > job.allowance.usd_nano or actual.credits > job.allowance.credits
                or any(p.actual and (p.actual.usd_nano > p.held.usd_nano or p.actual.credits > p.held.credits)
                       for p in report.wallet.payments.values()))
    escrow.unknown = unknown
    job.reconciliation_required = False
    if exceeded:
        state.blocked = True
    job.settled = not unknown
    if job.settled:
        escrow.actual = campaign.Amount()
    valid &= not unknown and not exceeded and job.state == "done"
    job.state = "done" if valid else "failed"
    job.failure = None if valid else "Re-check evidence or accounting is incomplete; inspect controller diagnostics"
    if valid:
        state.watch_report = published


def _store_report(lease_id: str, report: WorkerReport, body_hash: str) -> None:
    with campaign.transaction(settings.campaign_budget_file) as state:
        job = state.jobs.get(lease_id)
        if not job or state.retired_to:
            raise HTTPException(409, "Worker lease is unavailable")
        if job.report_hash and job.report_hash != body_hash:
            raise HTTPException(409, "A different terminal report already exists for this lease")
        _validate_report(job, report)
        _artifacts(job, report)
        if not job.report_hash:
            stored = report.model_dump_json().encode()
            relative = f"reports/{job.lease_id}/{body_hash}.json"
            target = settings.controller_state_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != stored:
                    raise budget.BudgetExceeded("Worker receipt path is corrupt; allowance retained")
                with target.open("rb") as output:
                    os.fsync(output.fileno())
            else:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(stored)
                    output.flush()
                    os.fsync(output.fileno())
            from .authority import sync_directory
            for directory in (target.parent, target.parent.parent, settings.controller_state_dir):
                sync_directory(directory)
            job.report_path, job.report_digest = relative, hashlib.sha256(stored).hexdigest()
            job.report_hash = body_hash
            job.report_at, job.run_id, job.duration_ms = report.checked_at, report.run_id, report.duration_ms
        job.wallet_unknown = any(p.actual is None or p.unknown for p in report.wallet.payments.values())
        if job.wallet_unknown:
            state.payments[job.payment_id].unknown = True


def require_reconciliation(lease_id: str) -> None:
    # Persist the block separately when receipt storage or finalization rolled back.
    with campaign.transaction(settings.campaign_budget_file) as state:
        job = state.jobs[lease_id]
        if not job.settled:
            job.reconciliation_required = True
            state.payments[job.payment_id].unknown = True
            job.failure = "Worker receipt or archive could not be verified; allowance retained"


def receive(lease_id: str, report: WorkerReport, body_hash: str) -> dict:
    try:
        _store_report(lease_id, report, body_hash)
    except budget.BudgetExceeded:
        require_reconciliation(lease_id)
        raise
    return finalize(lease_id)


def finalize(lease_id: str) -> dict:
    try:
        with campaign.transaction(settings.campaign_budget_file) as state:
            job = state.jobs[lease_id]
            _finalize(state, job)
            return {"accepted": True, "settled": job.settled, "published": job.settled and job.state == "done"}
    except Exception:
        require_reconciliation(lease_id)
        raise


def observe(lease_id: str, **fields) -> None:
    with campaign.transaction(settings.campaign_budget_file) as state:
        job = state.jobs[lease_id]
        if job.settled:
            return
        for name, value in fields.items():
            setattr(job, name, value)
        state.payments[job.payment_id].unknown = (not job.state_known or job.cloud_terminal and job.report_path is None
                                                or job.wallet_unknown or job.reconciliation_required)
    finalize(lease_id)
