"""One app-launched re-check at a time, using the installed CLI. Never persist CLI payloads or credentials."""

import asyncio
import json
import logging
import os
import shlex
import tempfile
import time
from pathlib import Path

from fastapi import HTTPException

from .config import redact, settings
from . import job_control
from .providers import budget

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


def configured() -> bool:
    return bool(settings.live and profile_ready and settings.speccheck_image and job_control.controller_origin(settings.speccheck_url)
                and settings.secret("admin_token") and job_control.configured()
                and all(getattr(settings, f"nebius_secret_{key}") for key in ("nebius_api_key", "tavily_api_key", "worker_token")))


def available() -> bool:
    return configured() and not budget.today().get("blocked", True)


def read_jobs() -> list[dict]:
    return [job_control.public(job) for job in job_control.records()]


def apply_status(job: dict, payload: dict) -> None:
    raw = payload.get("status", {}).get("state")
    if isinstance(raw, str):
        job["raw_state"] = redact(raw)[:200]
        mapped = settings.nebius_job_state_map.get(raw)
        job["state_known"] = mapped is not None
        if mapped:
            job["state"] = mapped
        # Unknown states remain in flight. Never infer that cloud compute has stopped.


async def refresh() -> list[dict]:
    global _last_poll
    if not configured() or time.monotonic() - _last_poll < 15:
        return read_jobs()
    _last_poll = time.monotonic()
    for record in job_control.records():
        if record.settled:
            continue
        if record.cloud_terminal:
            job_control.finalize(record.lease_id)
            continue
        job = job_control.public(record)
        try:
            if not job.get("id"):
                job["id"] = (await cli("ai", "job", "get-by-name", "--name", job["name"], "--profile", "speccheck",
                                       "--format", "jsonpath={.metadata.id}")).strip() or None
            if job.get("id"):
                payload = json.loads(await cli("ai", "job", "get", job["id"], "--profile", "speccheck", "--format", "json"))
                apply_status(job, payload)
                job.pop("poll_error", None)
                job["cloud_terminal"] = job["state_known"] and job["state"] in ("done", "failed")
        except (RuntimeError, ValueError, TypeError, AttributeError):
            job["poll_error"] = "Could not refresh the job; its last known state is shown."
            job["state_known"] = False
        job_control.observe(record.lease_id, **{k: v for k, v in job.items() if k in (
            "id", "state", "raw_state", "state_known", "cloud_terminal", "poll_error")})
    return read_jobs()


def command(job) -> list[str]:
    if not all(getattr(settings, f"nebius_secret_{key}") for key in ("nebius_api_key", "tavily_api_key", "worker_token")):
        raise HTTPException(409, "Cloud jobs require MysteryBox selectors for all three credentials.")
    args = ["ai", "job", "create", "--profile", "speccheck", "--name", job.name, "--image", job.image,
            "--container-command", "python", "--args", shlex.join(["scripts/recheck.py", "--controller", settings.speccheck_url,
                                                                       "--lease", job.lease_id]),
            "--platform", "cpu-d3", "--preset", "2vcpu-8gb", "--disk-size", "32Gi", "--timeout", "1h",
            "--restart-policy", "never", "--on-demand", "--async", "--format", "json"]
    env = {"SPECCHECK_MODE": "live", "RECHECK_RUNNER": "Nebius Serverless Job", "JOB_NAME": job.name}
    profile = job.manifest["config"]
    env.update({key.upper(): str(value) for key, value in profile.items() if key not in ("models", "prices")})
    env.update({f"MODEL_{role.upper()}": model for role, model in profile["models"].items()})
    if job.manifest.get("commit"):
        env["SPECCHECK_COMMIT"] = job.manifest["commit"]
    for key, value in env.items():
        args += ["--env", f"{key}={value}"]
    for key in ("nebius_api_key", "tavily_api_key", "worker_token"):
        selector = getattr(settings, f"nebius_secret_{key}")
        args += ["--env-secret", f"{key.upper()}={selector}"]
    return args


async def start(request_id: str) -> dict:
    if not configured():
        raise HTTPException(409, "Nebius jobs need live mode, a configured profile, SPECCHECK_IMAGE and SPECCHECK_URL.")
    async with lock:
        # A repeated request is returned even while an unknown existing operation blocks new admissions.
        previous = next((job for job in job_control.records() if job.request_id == request_id), None)
        if previous:
            return job_control.public(previous)
        await refresh()
        job, created = job_control.reserve(request_id)
        if not created:
            return job_control.public(job)
        try:
            payload = json.loads(await cli(*command(job)))
            # --async --format json returns an Operation; its id is NOT the job id.
            if not isinstance(payload.get("resource_id"), str) or not payload["resource_id"]:
                raise RuntimeError("Job creation did not confirm a resource ID")
            job_control.observe(job.lease_id, id=payload["resource_id"])
        except (RuntimeError, ValueError, TypeError, AttributeError):
            job_control.observe(job.lease_id, poll_error="Creation not confirmed; checking by job name.", state_known=False)
        return next(row for row in read_jobs() if row["name"] == job.name)


async def list_jobs() -> dict:
    async with lock:
        return {"available": available(), "jobs": (await refresh())[:5]}
