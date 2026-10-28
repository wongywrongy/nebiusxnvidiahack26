"""Launch one real re-check job from this machine through the server's own code path, and follow it to the end.

  export NEBIUS_SA_ID=… NEBIUS_PUBLIC_KEY_ID=… NEBIUS_PROJECT_ID=… SPECCHECK_IMAGE=… SPECCHECK_URL=… \
         RECHECK_MYSTERYBOX_SECRET_ID=…
  export NEBIUS_PRIVATE_KEY="$(cat sa.pem)"      # read from the environment, never printed
  python scripts/launch_recheck.py

Creates speccheck-recheck-manual-<UTC time> with api/daily_recheck.create (the code the server runs daily),
waits for a terminal state, then waits for that job's report on SPECCHECK_URL. Exit 0 only when the report is
live; otherwise it names the assumption that broke. Costs one job: at most $0.50 and 40 Tavily credits.
The app accepts this report only while it runs a build without the launch check (before the Package H
redeploy); after it, only jobs the server launched itself may report.
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import daily_recheck  # noqa: E402
from api.config import settings  # noqa: E402

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "ERROR"}
LOGS = "nebius ai job logs {id}"


def missing() -> list[str]:
    values = {"NEBIUS_SA_ID": settings.nebius_sa_id, "NEBIUS_PUBLIC_KEY_ID": settings.nebius_public_key_id,
              "NEBIUS_PRIVATE_KEY": settings.secret("nebius_private_key"), "NEBIUS_PROJECT_ID": settings.nebius_project_id,
              "SPECCHECK_IMAGE": settings.speccheck_image, "SPECCHECK_URL": settings.speccheck_url,
              "RECHECK_MYSTERYBOX_SECRET_ID": settings.recheck_mysterybox_secret_id}
    return [name for name, value in values.items() if not value]


def create_failure(code: str, message: str) -> str:
    if code == "UNAUTHENTICATED":
        return "Key: NEBIUS_PRIVATE_KEY, NEBIUS_PUBLIC_KEY_ID and NEBIUS_SA_ID do not match the uploaded public key."
    if code == "PERMISSION_DENIED":
        return "Role: the service account may not create jobs in this project. Add it to the editors group."
    if code in ("UNAVAILABLE", "DEADLINE_EXCEEDED"):
        return "Network: this machine could not reach api.nebius.cloud."
    if code == "NOT_FOUND":
        return f"Naming: NEBIUS_PROJECT_ID or RECHECK_MYSTERYBOX_SECRET_ID does not exist ({message})."
    return f"Job spec rejected ({code}): {message}"


def job_failure(state: str, details: str) -> str:
    text = details.lower()
    secret = any(word in text for word in ("mysterybox", "secret", "payload"))
    if secret and any(word in text for word in ("permission", "denied", "forbidden", "access")):
        return "Role: the service account cannot read the MysteryBox payload. Add it to a group with mysterybox.payload-viewer."
    if secret:
        return ("Env var naming: the secret must hold payload keys named exactly NEBIUS_API_KEY, TAVILY_API_KEY and "
                "ADMIN_TOKEN.")
    if any(word in text for word in ("image", "pull", "registry", "manifest")):
        return "Network: the job could not pull SPECCHECK_IMAGE."
    return f"The container exited with {state}; the logs show why."


NO_REPORT = ("Network or admin token: the job completed but its report never reached SPECCHECK_URL. In the logs, "
             "'posted re-check report: HTTP 403' means the ADMIN_TOKEN payload differs from the app's admin token; "
             "a connection error means the job cannot reach the URL.")


async def follow(job_id: str, *, poll_s: float = 15, limit_s: float = 75 * 60) -> tuple[str, str]:
    from nebius.api.nebius.ai.v1 import GetJobRequest

    last, details, deadline = "", "", time.monotonic() + limit_s
    async with daily_recheck.jobs() as client:
        while time.monotonic() < deadline:
            status = (await client.get(GetJobRequest(id=job_id))).status
            state = status.state.name
            details = " ".join(filter(None, (status.state_details.code, status.state_details.message))) if status.state_details else ""
            if state != last:
                print(f"{datetime.now(timezone.utc):%H:%M:%S} {state}{f' — {details}' if details else ''}", flush=True)
                last = state
            if state in TERMINAL:
                return state, details
            await asyncio.sleep(poll_s)
    return last or "UNKNOWN", details


def report_for(runner: str, *, tries: int = 20, poll_s: float = 15) -> dict | None:
    for _ in range(tries):
        r = httpx.get(settings.speccheck_url.rstrip("/") + "/api/watch", timeout=30)
        if r.status_code == 200 and r.json().get("runner") == runner:
            return r.json()
        time.sleep(poll_s)
    return None


async def main() -> int:
    if gaps := missing():
        print("Set these first:", ", ".join(gaps))
        return 2
    name = f"speccheck-recheck-manual-{datetime.now(timezone.utc):%Y%m%dt%H%M%S}"
    try:
        job_id = await daily_recheck.create(name)
    except Exception as e:  # the SDK's RequestError carries the gRPC status
        status = getattr(e, "status", None)
        code = getattr(getattr(status, "code", None), "name", type(e).__name__)
        print(f"Create failed ({code}).\n{create_failure(code, getattr(status, 'message', None) or '')}")
        return 1
    print(f"Created {name} ({job_id}). Logs: {LOGS.format(id=job_id)}")
    state, details = await follow(job_id)
    if state != "COMPLETED":
        print(f"Job ended {state}.\n{job_failure(state, details) if state in TERMINAL else 'Still running at the time limit.'}"
              f"\nLogs: {LOGS.format(id=job_id)}")
        return 1
    report = report_for(daily_recheck.PREFIX + name)
    if not report:
        print(f"{NO_REPORT}\nLogs: {LOGS.format(id=job_id)}")
        return 1
    print(f"Report live on {settings.speccheck_url}: {report['checked_at']} · "
          + ", ".join(f"{i['id']} {i['status']}" for i in report["items"]))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
