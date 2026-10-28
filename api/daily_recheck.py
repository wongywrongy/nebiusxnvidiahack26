"""Once a day the server launches the re-check as a Nebius Serverless Job. Nebius jobs have no schedule of their own.

The job runs scripts/recheck.py from the same public image with its own capped ledger ($0.50, 40 Tavily credits),
reads its keys from MysteryBox, and posts its report back with the admin token. The launch is recorded before
the create call, so a crash or restart can never launch twice in one UTC day.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from datetime import datetime, timedelta, timezone

from . import watch_store
from .config import settings

log = logging.getLogger("speccheck.recheck")
PREFIX = "Nebius Serverless Job "
CAP_USD, CAP_CREDITS = 0.5, 40
LAUNCHES = "launches.json"


def configured() -> bool:
    return bool(settings.live and settings.nebius_sa_id and settings.nebius_public_key_id and settings.secret("nebius_private_key")
                and settings.nebius_project_id and settings.speccheck_image and settings.speccheck_url
                and settings.recheck_mysterybox_secret_id)


def launched_names() -> set[str]:
    return {row["name"] for row in watch_store.read(LAUNCHES, {}).values()}


def job_request(name: str):
    from nebius.api.nebius.ai.v1 import CreateJobRequest, JobSpec
    from nebius.api.nebius.common.v1 import ResourceMetadata
    from nebius.api.nebius.compute.v1 import DiskSpec__DiskType as DiskType

    Env, Ref = JobSpec.EnvironmentVariable, JobSpec.MysteryBoxSecretRef

    plain = {"SPECCHECK_MODE": "live", "RECHECK_RUNNER": PREFIX + name, "BUDGET_USD_PER_RUN": str(CAP_USD),
             "BUDGET_TAVILY_CREDITS_PER_ITEM": str(CAP_CREDITS)}
    # The env name must match the payload key inside the MysteryBox secret.
    secret = Ref(secret_id=settings.recheck_mysterybox_secret_id)
    env = [Env(name=k, value=v) for k, v in plain.items()] + [
        Env(name=k, mysterybox_secret=secret) for k in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "ADMIN_TOKEN")]
    script = (f"python scripts/campaign_budget.py init-judging --usd {CAP_USD} --credits {CAP_CREDITS} >/dev/null"
              f" && python scripts/recheck.py --post {shlex.quote(settings.speccheck_url)}")
    return CreateJobRequest(
        metadata=ResourceMetadata(parent_id=settings.nebius_project_id, name=name),
        spec=JobSpec(image=settings.speccheck_image, container_command="bash", args=shlex.join(["-c", script]),
                     environment_variables=env, platform="cpu-d3", preset="2vcpu-8gb",
                     disk=JobSpec.DiskSpec(type=DiskType.NETWORK_SSD, size_bytes=32 * 1024**3),
                     restart_attempts=0, timeout=timedelta(hours=1)))


async def create(name: str) -> str:
    from cryptography.hazmat.primitives import serialization
    from nebius.api.nebius.ai.v1 import JobServiceClient
    from nebius.base.service_account.service_account import ServiceAccount
    from nebius.sdk import SDK

    key = serialization.load_pem_private_key(settings.secret("nebius_private_key").encode(), password=None)
    sdk = SDK(credentials=ServiceAccount(key, settings.nebius_public_key_id, settings.nebius_sa_id), user_agent_prefix="speccheck/1.0")
    try:
        operation = await JobServiceClient(sdk).create(job_request(name))
        return operation.resource_id
    finally:
        await sdk.close()


async def launch_if_due(now: datetime | None = None) -> dict | None:
    """Launch today's job once it is past the hour. Returns the launch record, or None when nothing was due."""
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    launches = watch_store.read(LAUNCHES, {})
    if now.hour < settings.recheck_hour_utc or day in launches:
        return None
    record = {"name": f"speccheck-recheck-{day}", "at": now.isoformat(timespec="seconds")}
    watch_store.write(LAUNCHES, {**launches, day: record})  # before the call: at most one launch per day
    try:
        record["id"] = await create(record["name"])
    except Exception as e:  # recorded, not retried today
        record["error"] = type(e).__name__
        log.warning("Daily re-check launch failed (%s); next attempt tomorrow", type(e).__name__)
    watch_store.write(LAUNCHES, {**launches, day: record})
    return record


async def loop() -> None:
    while True:
        try:
            await launch_if_due()
        except OSError:
            log.warning("Daily re-check state unavailable; will retry")
        await asyncio.sleep(600)
