"""One app-launched re-check at a time, using the installed CLI. Never persist CLI payloads or credentials."""

import asyncio
import json
import logging
import os
import shlex
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

from .config import redact, settings
from . import watch_store

log = logging.getLogger("speccheck.jobs")
lock = asyncio.Lock()
profile_ready = False
_profile_dir: tempfile.TemporaryDirectory | None = None
_last_poll = 0.0


async def cli(*args: str) -> str:
    """No shell, bounded wait, and no command/stdout/stderr in logs or exceptions."""
    try:
        config = ["--config", str(Path(_profile_dir.name) / "config.yaml")] if _profile_dir else []
        proc = await asyncio.create_subprocess_exec(
            "nebius", *args, *config, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), 45)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            await proc.communicate()
            raise
        if proc.returncode:
            raise RuntimeError("Nebius CLI could not complete the request")
        return out.decode()
    except (OSError, asyncio.TimeoutError) as e:
        raise RuntimeError("Nebius CLI unavailable or timed out") from e


async def setup_profile() -> None:
    global profile_ready, _profile_dir, lock, _last_poll
    lock, _last_poll = asyncio.Lock(), 0.0
    profile_ready = False
    if not (settings.live and settings.nebius_sa_id and settings.nebius_public_key_id
            and settings.secret("nebius_private_key") and settings.nebius_project_id):
        return
    _profile_dir = tempfile.TemporaryDirectory(prefix="speccheck-sa-")
    pem = Path(_profile_dir.name) / "key.pem"
    fd = os.open(pem, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(settings.secret("nebius_private_key"))
    try:
        await cli("profile", "create", "--endpoint", "api.nebius.cloud", "--service-account-id", settings.nebius_sa_id,
                  "--public-key-id", settings.nebius_public_key_id, "--private-key-file", str(pem),
                  "--parent-id", settings.nebius_project_id, "--profile", "speccheck", "--no-browser")
        profile_ready = True  # The CLI profile references the PEM, so retain it until shutdown.
    except RuntimeError:
        log.warning("Nebius profile unavailable; job action disabled")
        cleanup_profile()


def cleanup_profile() -> None:
    global _profile_dir, profile_ready
    profile_ready = False
    if _profile_dir:
        _profile_dir.cleanup()
        _profile_dir = None


def available() -> bool:
    url = urlparse(settings.speccheck_url)
    return bool(settings.live and profile_ready and settings.speccheck_image and url.scheme in ("http", "https")
                and url.hostname and not url.username and not url.password and not url.query and not url.fragment
                and (settings.secret("admin_token") or settings.nebius_secret_admin_token))


def read_jobs() -> list[dict]:
    return watch_store.read("jobs.json", [])


def write_jobs(jobs: list[dict]) -> None:
    watch_store.write("jobs.json", jobs[:5])


def apply_status(job: dict, payload: dict) -> None:
    raw = payload.get("status", {}).get("state")
    if isinstance(raw, str):
        job["raw_state"] = redact(raw)[:200]
        mapped = settings.nebius_job_state_map.get(raw)
        job["state_known"] = mapped is not None
        if mapped:
            job["state"] = mapped
        # Unknown states remain in flight. Never infer that cloud compute has stopped.


async def refresh(jobs: list[dict]) -> list[dict]:
    global _last_poll
    if not available() or time.monotonic() - _last_poll < 15:
        return jobs
    _last_poll = time.monotonic()
    for job in jobs[:5]:
        if job["state"] in ("done", "failed"):
            continue
        try:
            if not job.get("id"):
                job["id"] = (await cli("ai", "job", "get-by-name", "--name", job["name"], "--profile", "speccheck",
                                       "--format", "jsonpath={.metadata.id}")).strip() or None
            if job.get("id"):
                payload = json.loads(await cli("ai", "job", "get", job["id"], "--profile", "speccheck", "--format", "json"))
                apply_status(job, payload)
                job.pop("poll_error", None)
        except (RuntimeError, ValueError, TypeError, AttributeError):
            job["poll_error"] = "Could not refresh the job; its last known state is shown."
    write_jobs(jobs)
    return jobs


def command(name: str) -> list[str]:
    args = ["ai", "job", "create", "--profile", "speccheck", "--name", name, "--image", settings.speccheck_image,
            "--container-command", "python", "--args", shlex.join(["scripts/recheck.py", "--post", settings.speccheck_url]),
            "--platform", "cpu-d3", "--preset", "2vcpu-8gb", "--disk-size", "32Gi", "--timeout", "1h",
            "--restart-policy", "never", "--on-demand", "--async", "--format", "json"]
    env = {"SPECCHECK_MODE": "live", "THINKING": settings.thinking, "RECHECK_RUNNER": "Nebius Serverless Job", "JOB_NAME": name}
    for key in ("budget_usd_per_run", "budget_usd_per_day", "budget_tavily_credits_per_item",
                "budget_tavily_credits_per_day", "max_concurrency", "thinking_tasks", "max_page_chars", "web_source_chars",
                "search_depth", "extract_depth", "search_max_results", "investigate_credit_cap", "investigate_max_steps", "map_limit"):
        env[key.upper()] = str(getattr(settings, key))
    if settings.nebius_evidence_bucket:
        args += ["--volume", f"s3://{settings.nebius_evidence_bucket}:/app/evidence:rw"]
        env.update(EVIDENCE_DIR="/app/evidence", EVIDENCE_LABEL="Nebius Object Storage")
    for key, value in env.items():
        args += ["--env", f"{key}={value}"]
    for key in ("nebius_api_key", "tavily_api_key", "admin_token"):
        selector = getattr(settings, f"nebius_secret_{key}")
        if selector:
            args += ["--env-secret", f"{key.upper()}={selector}"]
        else:
            log.warning("%s has no MysteryBox selector; falling back to --env", key.upper())
            args += ["--env", f"{key.upper()}={settings.secret(key)}"]
    return args


async def start() -> dict:
    if not available():
        raise HTTPException(409, "Nebius jobs need live mode, a configured profile, SPECCHECK_IMAGE and SPECCHECK_URL.")
    async with lock:
        jobs = await refresh(read_jobs())
        if any(j["state"] not in ("done", "failed") for j in jobs):
            raise HTTPException(409, "A Nebius re-check is already in flight.")
        now = datetime.now(timezone.utc)
        if jobs and (now - datetime.fromisoformat(jobs[0]["created_at"])).total_seconds() < settings.watch_run_interval_s:
            raise HTTPException(429, "A Nebius job was requested recently. Try again after the job rate-limit interval.")
        job = {"name": f"speccheck-recheck-{now.strftime('%Y%m%d-%H%M%S-%f')}", "id": None,
               "created_at": now.isoformat(), "state": "queued", "raw_state": None, "state_known": True}
        jobs.insert(0, job)
        write_jobs(jobs)  # Reserve before awaiting create; ambiguous CLI failure must not create duplicate jobs.
        try:
            payload = json.loads(await cli(*command(job["name"])))
            # --async --format json returns an Operation; its id is NOT the job id.
            job["id"] = payload.get("resource_id") or None
        except (RuntimeError, ValueError, TypeError, AttributeError):
            job["poll_error"] = "Creation not confirmed; checking by job name."
        write_jobs(jobs)
        return job


async def list_jobs() -> dict:
    async with lock:
        return {"available": available(), "jobs": await refresh(read_jobs())}


async def attach_report(report: dict) -> None:
    if not report.get("job_name"):
        return
    async with lock:
        jobs = read_jobs()
        job = next((j for j in jobs if j["name"] == report["job_name"]), None)
        if job is None:
            job = {"name": report["job_name"], "id": None, "created_at": report["checked_at"],
                   "state": "running", "raw_state": None, "state_known": True}
            jobs.insert(0, job)
        job.update(report_at=report["checked_at"], run_id=report.get("run_id"), duration_ms=report.get("duration_ms"))
        write_jobs(jobs)
