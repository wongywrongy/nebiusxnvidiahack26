"""Runs cases through the pipeline, streams events, and records everything for replay.

A run writes to runs/<run_id>/:
  events.jsonl         every event, in order, with timing (this is the replay recording)
  results/<case>.json  the final result for each case
Live runs recorded for the public demo (scripts/record_live.py) are committed under runs/recorded/<run_id>/.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
import shutil
import logging
from contextlib import nullcontext
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Iterable, Optional

from ..config import FORCE_MOCK, redact, settings
from .. import archive, cache, readiness
from ..providers import ProviderError, budget, failure_reason
from ..providers.budget import BudgetExceeded
from ..schemas import Diagnostic, Event, Investigation, ReportOut, Requirement, Result, Usage
from . import checklists, decide, extract, fix, metrics, spec_check, verify
from .cases import all_specs, get_case
from .ingest import load_spec_text, load_submittal_pages, submittal_pdfs
from .render import attach_highlights

MAX_DISK_RUNS = 500
ACTIVE_RUNS: set[str] = set()
REPLAY_READERS: Counter[str] = Counter()
log = logging.getLogger("speccheck.runs")


class Run:
    def __init__(self, case_ids: list[str], delay_ms: Optional[int] = None, mock: Iterable[str] = (),
                 shared_item_budget: bool = False, replay_of: str | None = None, refresh_web: bool = False,
                 catalog: dict[str, dict] | None = None):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.case_ids = case_ids
        self.catalog = catalog
        self.mock = set(mock)  # items forced to mock mode even when the server is live (public uploads)
        self.shared_item_budget = shared_item_budget
        self.replay_of = replay_of
        self.refresh_web = refresh_web
        self.ledger = budget.Ledger(self.id)
        self.delay_ms = settings.mock_stage_delay_ms if delay_ms is None else delay_ms
        self.events: list[Event] = []
        self.results: dict[str, Result] = {}
        self.attempts: dict[str, dict] = {}
        self.manifest = readiness.manifest()
        self.manifest.update(refresh_web=refresh_web, run_id=self.id, requested_ids=case_ids,
                             started_at=datetime.now(timezone.utc).isoformat())
        self.done = asyncio.Event()
        self._subscribers: list[asyncio.Queue] = []
        self._t0 = time.perf_counter()
        self.dir = settings.runs_dir / self.id
        (self.dir / "results").mkdir(parents=True, exist_ok=True)
        (self.dir / "manifest.json").write_text(json.dumps(self.manifest, indent=2))
        ACTIVE_RUNS.add(self.id)
        if replay_of:
            REPLAY_READERS[replay_of] += 1
        prune_runs()

    def emit(self, stage: str, message: str, case_id: Optional[str] = None, model: Optional[str] = None,
             data: Optional[dict] = None, t_ms: Optional[int] = None) -> Event:
        ev = Event(run_id=self.id, case_id=case_id, stage=stage, message=redact(message), model=model, data=data,
                   t_ms=int((time.perf_counter() - self._t0) * 1000) if t_ms is None else t_ms)
        self.events.append(ev)
        with (self.dir / "events.jsonl").open("a") as f:
            f.write(ev.model_dump_json() + "\n")
        for q in self._subscribers:
            q.put_nowait(ev)
        return ev

    async def stream(self) -> AsyncIterator[Event]:
        """All events so far, then live ones until the run finishes."""
        q: asyncio.Queue = asyncio.Queue()
        # Subscribe and snapshot with no await in between, so no event is missed or sent twice.
        self._subscribers.append(q)
        history = list(self.events)
        try:
            for ev in history:
                yield ev
            while not (self.done.is_set() and q.empty()):
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                yield ev
        finally:
            self._subscribers.remove(q)

    async def pause(self) -> None:
        if not settings.live and self.delay_ms:
            await asyncio.sleep(self.delay_ms / 1000)


async def run_case(run: Run, case_id: str, sem: asyncio.Semaphore) -> Result:
    case = run.catalog[case_id] if run.catalog is not None else get_case(case_id)
    usage: list[Usage] = []
    investigations: list[Investigation] = []
    warnings: list[str] = []
    diagnostics: list[Diagnostic] = []
    counts = dict.fromkeys(metrics.FIELDS, 0)
    count_token = metrics.COUNTS.set(counts)

    async def investigating(tool: str):
        run.emit("investigate", f"Investigating: {tool} …", case_id, settings.models["verify"])
        await run.pause()
    async def warn(stage: str, reason: str):
        message = f"{stage}: {reason}; couldn't confirm"
        warnings.append(message)
        kind = "budget" if re.search(r"budget|cap", reason, re.I) else "output_limit" if "cut off" in reason else "provider"
        diagnostics.append(Diagnostic(stage=stage, kind=kind, message=redact(reason)))
        run.emit(stage.split(".")[0], message, case_id, data={"warning": True, "stage": stage})
    budget.ITEM.set(case_id)  # this task's own context: credit caps are per item
    FORCE_MOCK.set(case_id in run.mock)
    async with sem:
        t0 = time.perf_counter()
        queue_ms = int((t0 - run._t0) * 1000)
        stage = "ingest"
        fx = case.get("fixture", case_id)  # which recorded answers mock mode uses; None for an unknown upload
        try:
            run.emit("ingest", "Reading the pages", case_id)
            pages = await load_submittal_pages(case)
            ocr_pages = {p["page"] for p in pages if p.get("ocr")}
            if settings.live and not any(p["text"].strip() for p in pages):
                raise RuntimeError("No readable text in the submittal: the PDF is missing or OCR could not read its pages")
            await run.pause()

            run.emit("triage", "Sorting pages", case_id, settings.models["triage"])
            stage = "triage"
            labels, u = await extract.triage(fx, pages)
            usage.append(u)
            await run.pause()

            run.emit("extract", "Comparing to the spec", case_id, settings.models["extract"])
            stage = "extract"
            if case.get("checklist_id"):
                if not case.get("upload"):
                    raise ValueError("Draft checklists can only be used for uploaded PDFs")
                reqs = checklists.load_upload(case["checklist_id"])
                spec = {"title": reqs.title}
                requirements = reqs.requirements
                case = {**case, "section": reqs.section, "conditions": [], "not_applicable": [], "manufacturer_domains": []}
            else:
                spec = all_specs()[case["section"]]
                spec_text = await load_spec_text(case["section"], spec)
                reqs, u = await extract.requirements_for(case["section"], spec_text)
                if u:
                    usage.append(u)
                # Project-specific conditions come from the case cover sheet, never a public draft.
                requirements = reqs.requirements + [Requirement(**c) for c in case.get("conditions", [])]
                skip = set(case.get("not_applicable", []))
                requirements = [r for r in requirements if r.property not in skip]
            props = spec_check.properties_for(requirements)
            claims, u = await extract.extract_claims(fx, pages, labels, props)
            usage += u

            stage = "spec_check"
            roles = {d["role"] for d in case["submittal"]} | {p.kind for p in labels.pages}
            findings = spec_check.check(requirements, claims.claims, roles)
            matched = sum(bool(f.claim_ids or f.claim_id) for f in findings)
            run.emit("spec_check", f"Checked against {case['section']}: {matched} of {len(requirements)} rules matched",
                     case_id, "code", data={"section": case["section"], "title": spec["title"],
                                           "rules": len(requirements), "matched": matched,
                                           "checklist_id": case.get("checklist_id")})
            await run.pause()

            vf, rows, credits, verification = [], [], 0.0, []
            if decide.decide(findings) != "not_applicable":
                tally = {v: sum(f.verdict == v for f in findings) for v in ("pass", "fail", "unverified")}
                run.emit("verify", "Checking the manufacturer online", case_id, f"tavily + {settings.models['verify']}",
                         data={"spec": tally})
                try:
                    stage = "verify"
                    vf, rows, u, credits, inv = await verify.verify(case, claims, on_step=investigating, on_warning=warn,
                                                                  on_proof=verification.append)
                    usage += u
                    if inv is not None:
                        investigations.append(inv)
                except (BudgetExceeded, ProviderError) as e:
                    await warn("verify", failure_reason(e))
                    vf, rows, credits = [verify.unconfirmed(failure_reason(e))], [], run.ledger.credits.get(case_id, 0.0)
                findings += vf
                await run.pause()

            decision = decide.decide(findings)
            ev = next((f.evidence for f in vf if f.evidence), [])
            web = {"sheet": next((f.title for f in vf), ""), "verdict": next((f.verdict for f in vf), ""),
                   "sources": [{"url": e.url, "tier": e.tier} for e in ev]}
            if decision == "send_back":
                run.emit("fix", "Finding a fix", case_id, f"tavily + {settings.models['verify']}", data={"web": web})
                try:
                    stage = "fix"
                    u, fix_credits = await fix.find_fixes(case, requirements, claims, findings,
                                                          settings.fix_max_candidates, settings.fix_credit_cap,
                                                          investigations=investigations, on_step=investigating, on_warning=warn)
                    usage += u
                    credits += fix_credits
                except (BudgetExceeded, ProviderError) as e:
                    await warn("fix", failure_reason(e))
                    credits = run.ledger.credits.get(case_id, credits)
                await run.pause()

            fixed = next((f.fix for f in findings if f.fix), None)
            run.emit("report", "Writing the result", case_id, settings.models["write"],
                     data={"web": web, **({"fix": fixed.head} if fixed else {})})
            try:
                stage = "report"
                rep, u = await decide.report(fx, case["title"], decision, findings)
                usage += u
            except (BudgetExceeded, ProviderError) as e:
                await warn("report", failure_reason(e))
                rep = ReportOut(summary=f"{warnings[-1]}. The decision and findings above stand.",
                                note_to_subcontractor="")
            attach_highlights(case, claims.claims, findings, ocr_pages=ocr_pages)
            await run.pause()

            investigation = None
            if investigations:
                steps = [s.model_copy(update={"n": n}) for n, s in enumerate(
                    (s for inv in investigations for s in inv.steps), start=1)]
                outcomes = {inv.outcome for inv in investigations}
                investigation = Investigation(steps=steps, outcome=("capped" if "capped" in outcomes else
                                                                    "found" if "found" in outcomes else "not_found"))
            archived_submittals = []
            if settings.evidence_dir and (decision in ("approve", "approve_with_note") or case.get("watch")):
                for path in submittal_pdfs(case):
                    try:
                        saved = archive.save(case_id, path.read_bytes(), "pdf")
                        if saved:
                            archived_submittals.append(saved)
                    except OSError:
                        warnings.append("Could not archive the submittal PDF.")
            archived = archived_submittals or any(e.archived_path for f in findings for e in f.evidence)
            for reason in run.ledger.accounting_issues.get(case_id, []):
                diagnostics.append(Diagnostic(stage="accounting", kind="provider", message=reason))
            result = Result(
                case_id=case_id, title=case["title"], decision=decision, summary=rep.summary, findings=findings,
                spec_section=case["section"], spec_title=spec["title"], spec_rule_count=len(requirements),
                spec_match_count=matched, checklist_id=case.get("checklist_id"),
                comparison=rows, claims=claims.claims, selection=claims.selection, document_revision=claims.document_revision,
                document_roles=sorted(roles),
                extracted=claims, verification=verification[0] if verification else None,
                note_to_subcontractor=rep.note_to_subcontractor, usage=usage, web_credits=credits,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                investigation=investigation, investigations=investigations,
                mode="live" if settings.live else "mock", warnings=warnings,
                diagnostics=diagnostics, validity="invalid" if diagnostics else "valid", queue_ms=queue_ms,
                config_hash=run.manifest["config_hash"],
                fresh_model_cost_usd=run.ledger.fresh_usd.get(case_id, 0.0),
                fresh_web_credits=run.ledger.fresh_credits.get(case_id, 0.0),
                ocr_pages=len(ocr_pages),
                archived_submittals=archived_submittals, evidence_label=settings.evidence_label if archived else None,
                **counts,
            )
            (run.dir / "results" / f"{case_id}.json").write_text(result.model_dump_json(indent=2))
            run.results[case_id] = result
            # The run log keeps tokens, cost and credits for every call.
            run.emit("done", decision, case_id, data={"decision": decision, "summary": rep.summary,
                                                      "usage": [u.model_dump() for u in usage], "web_credits": credits})
            return result
        except Exception as e:  # keep the other cases running
            reason = failure_reason(e)
            diagnostics.append(Diagnostic(stage=stage, kind="budget" if isinstance(e, BudgetExceeded) else
                                          "provider" if isinstance(e, ProviderError) else "internal", message=reason))
            run.emit("error", reason, case_id, data={"reason": reason})
            raise
        finally:
            for reason in run.ledger.accounting_issues.get(case_id, []):
                diagnostic = Diagnostic(stage="accounting", kind="provider", message=reason)
                if diagnostic not in diagnostics:
                    diagnostics.append(diagnostic)
            run.attempts[case_id] = {"duration_ms": int((time.perf_counter() - t0) * 1000), "queue_ms": queue_ms,
                                     "fresh_model_cost_usd": run.ledger.fresh_usd.get(case_id, 0.0),
                                     "fresh_web_credits": run.ledger.fresh_credits.get(case_id, 0.0),
                                     "diagnostics": [d.model_dump() for d in diagnostics]}
            (run.dir / "attempts.json").write_text(json.dumps(run.attempts, indent=2))
            metrics.COUNTS.reset(count_token)


async def execute(run: Run) -> Run:
    refresh_token = cache.REFRESH_WEB.set(run.refresh_web)
    budget.LEDGER.set(run.ledger)  # inherited by every item task below
    sem = asyncio.Semaphore(1 if run.shared_item_budget else settings.max_concurrency)
    for cid in run.case_ids:
        run.emit("queued", "Waiting", cid)
    async def staggered(i: int, cid: str):
        if not settings.live and run.delay_ms:  # mock only: rows start a beat apart, as real calls would finish
            await asyncio.sleep(i * run.delay_ms / 1000 * 0.6)
        return await run_case(run, cid, sem)

    # A smoke scan checks two inputs under one run's USD cap and one item's total web allowance.
    try:
        with budget.credit_scope(settings.budget_tavily_credits_per_item) if run.shared_item_budget else nullcontext():
            await asyncio.gather(*(staggered(i, cid) for i, cid in enumerate(run.case_ids)), return_exceptions=True)
    finally:
        finish_run(run)
        cache.REFRESH_WEB.reset(refresh_token)
    return run


async def replay(run: Run, source_run_id: str, speed: float = 1.0, ids: Optional[list[str]] = None) -> Run:
    """Re-emit a recorded run's events with their original timing."""
    try:
        src = run_dir(source_run_id)
        events = [Event.model_validate_json(line) for line in (src / "events.jsonl").read_text().splitlines() if line]
        if ids is not None:
            events = [ev for ev in events if ev.case_id in ids]
        # Results first: the app fetches each one as soon as its "done" event arrives.
        for p in (src / "results").glob("*.json"):
            res = Result.model_validate_json(p.read_text())
            if ids is not None and res.case_id not in ids:
                continue
            res.replayed_from = source_run_id
            run.results[res.case_id] = res
            (run.dir / "results" / p.name).write_text(res.model_dump_json(indent=2))
        start = time.perf_counter()
        for ev in events:
            wait = ev.t_ms / 1000 / speed - (time.perf_counter() - start)
            if wait > 0:
                await asyncio.sleep(wait)
            run.emit(ev.stage, ev.message, ev.case_id, ev.model, ev.data)
        return run
    finally:
        finish_run(run)


RUN_ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")


def prune_runs() -> None:
    """Only generated run directories; never recordings, watch state, uploads or active work."""
    if not settings.runs_dir.exists():
        return
    try:
        folders = sorted((p for p in settings.runs_dir.iterdir()
                          if RUN_ID.fullmatch(p.name) and p.is_dir() and not p.is_symlink()),
                         key=lambda p: (p.name[:15], p.stat().st_mtime_ns), reverse=True)
        active = {p.name for p in folders if p.name in ACTIVE_RUNS or REPLAY_READERS[p.name]}
        keep = active | {p.name for p in [p for p in folders if p.name not in active][:max(0, MAX_DISK_RUNS - len(active))]}
        for path in folders:
            if path.name not in keep:
                shutil.rmtree(path)
    except OSError:
        log.warning("Run retention cleanup could not finish; check available disk space and permissions")


def finish_run(run: Run) -> None:
    run.done.set()
    ACTIVE_RUNS.discard(run.id)
    if run.replay_of:
        REPLAY_READERS[run.replay_of] -= 1
        if REPLAY_READERS[run.replay_of] <= 0:
            del REPLAY_READERS[run.replay_of]
    prune_runs()


def run_dir(run_id: str) -> Optional[Path]:
    """A run's folder (runs/<id>, else runs/recorded/<id>), or None. Only well-formed ids: they come from URLs."""
    if not RUN_ID.fullmatch(run_id):
        return None
    return next((d for d in (settings.runs_dir / run_id, settings.recorded_dir / run_id)
                 if (d / "events.jsonl").exists()), None)


def load_result(run_id: str, case_id: str) -> Optional[Result]:
    d = run_dir(run_id)
    p = d / "results" / f"{case_id}.json" if d else None
    try:
        return Result.model_validate_json(p.read_text()) if p and p.exists() else None
    except FileNotFoundError:  # retention may remove an old run between lookup and read
        return None


def _runs_in(folder: Path) -> list[str]:
    return [p.name for p in folder.iterdir() if (p / "events.jsonl").exists()] if folder.exists() else []


def recorded_runs() -> list[str]:
    """Committed live recordings, newest first."""
    return sorted(_runs_in(settings.recorded_dir), reverse=True)


def list_runs() -> list[str]:
    return sorted(_runs_in(settings.runs_dir) + _runs_in(settings.recorded_dir), reverse=True)
