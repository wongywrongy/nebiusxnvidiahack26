"""Leased worker: local allowance, sealed usage and immutable evidence; no controller disk or admin key."""

import asyncio
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid

import httpx

from .config import settings
from .providers import campaign
from .readiness import CONFIG_FIELDS, manifest
from .job_control import MAX_REPORT_BYTES, signature, controller_origin


async def _post(client, lease_id: str, action: str, body: bytes) -> dict:
    for attempt in range(2):
        try:
            response = await client.post(f"/api/watch/leases/{lease_id}/{action}", content=body,
                headers={"Content-Type": "application/json", "X-Worker-Signature": signature(lease_id, action, body),
                         "X-Worker-Proof": signature(lease_id, action, b"")})
            if response.status_code >= 500:
                raise httpx.HTTPError("Controller storage temporarily unavailable")
            if response.is_redirect or response.is_error:
                raise RuntimeError(f"Controller refused {action} (HTTP {response.status_code}); allowance retained")
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a controller object")
            return data
        except (httpx.HTTPError, ValueError):
            if attempt:
                raise RuntimeError(f"Controller {action} is unconfirmed; allowance retained") from None
            # The identical signed request is safe to retry; provider work is never restarted here.
            await asyncio.sleep(0)
    raise RuntimeError("Controller request did not complete")


async def execute(client, lease_id: str) -> int:
    from scripts import recheck

    if not settings.secret("worker_token") or settings.secret("admin_token") or settings.controller_state_dir:
        raise RuntimeError("A worker needs its own credential and must not receive admin or controller authority")
    session = uuid.uuid4().hex
    raw = json.dumps({"session": session}, sort_keys=True).encode()
    lease = await _post(client, lease_id, "claim", raw)
    profile = lease["manifest"]["config"]
    for name in CONFIG_FIELDS:
        setattr(settings, name, profile[name])
    for role, model in profile["models"].items():
        setattr(settings, f"model_{role}", model)
    settings.speccheck_mode = "live"
    if json.loads(json.dumps(manifest())) != lease["manifest"] or lease["lease_id"] != lease_id:
        raise RuntimeError("Worker code/configuration/documents do not match its lease; no provider call made")
    folder = Path(tempfile.mkdtemp(prefix="speccheck-worker-"))
    settings.campaign_budget_file = folder / "campaign.sqlite3"
    settings.cache_dir, settings.runs_dir = folder / "cache", folder / "runs"
    settings.evidence_dir, settings.evidence_label = folder / "evidence", "Controller archive"
    allowance = campaign.Amount.model_validate(lease["allowance"])
    campaign.initialize(settings.campaign_budget_file, campaign.Amount(), {}, allowance, allowance)
    started = time.perf_counter()
    failure = None
    try:
        report, result_run = await recheck.check(lease["ids"])
        run_id, results = result_run.id, {key: result.model_dump(mode="json") for key, result in result_run.results.items()}
    except Exception:
        # Report known charges even if the pipeline itself fails before producing its result.
        failure, results, report = "Worker pipeline failed", {}, {}
        with campaign.transaction(settings.campaign_budget_file) as state:
            run_id = next((payment.run for payment in state.payments.values()), uuid.uuid4().hex)
    with campaign.transaction(settings.campaign_budget_file) as state:
        state.blocked = True  # Seal before sending terminal usage; this process can make no more paid requests.
        wallet = state.model_dump(mode="json")
    artifacts = {str(path.relative_to(settings.evidence_dir)): base64.b64encode(path.read_bytes()).decode()
                 for path in settings.evidence_dir.rglob("*") if path.is_file()}
    from datetime import datetime, timezone
    payload = {"session": session, "run_id": run_id, "checked_at": report.get("checked_at") or datetime.now(timezone.utc).isoformat(),
        "manifest": lease["manifest"], "wallet": wallet, "results": results, "artifacts": artifacts,
        "duration_ms": int((time.perf_counter() - started) * 1000), "failure": failure}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(body) > MAX_REPORT_BYTES or any(value.encode() in body for name in ("nebius_api_key", "tavily_api_key", "worker_token")
                                          if (value := settings.secret(name))):
        raise RuntimeError("Worker report is oversized or contains credential material; allowance retained")
    (folder / "report.json").write_bytes(body)
    receipt = await _post(client, lease_id, "report", body)
    if receipt.get("accepted") is not True:
        raise RuntimeError("Controller did not acknowledge terminal usage; allowance retained")
    print(f"Worker report accepted; payload sha256={hashlib.sha256(body).hexdigest()}; cloud completion/publication still checked by controller")
    return 2 if failure or any(item["status"] == "unverified" for item in report.get("items", [])) else 0


async def run(base_url: str, lease_id: str) -> int:
    if not controller_origin(base_url):
        raise RuntimeError("Worker controller URL must be an HTTPS origin without credentials")
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=60, follow_redirects=False) as client:
        return await execute(client, lease_id)
