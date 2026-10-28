"""The server launches the daily re-check job at most once a UTC day, and only its own jobs may sign a report."""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import daily_recheck, main
from api.config import settings

client = TestClient(main.app)
CREATE = daily_recheck.create
TOKEN = "t-0123456789"  # synthetic test value; gitleaks:allow
PEM = "-----BEGIN PRIVATE KEY-----\nsynthetic-not-a-key\n-----END PRIVATE KEY-----"


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    monkeypatch.setattr(settings, "evidence_dir", None)
    for name, value in dict(speccheck_mode="live", nebius_sa_id="serviceaccount-x", nebius_public_key_id="publickey-x",
                            nebius_project_id="project-x", speccheck_image="ghcr.io/x/speccheck@sha256:" + "0" * 64,
                            speccheck_url="https://speccheck.example", recheck_mysterybox_secret_id="mbsec-x",
                            recheck_hour_utc=9).items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(settings, "nebius_private_key", SecretStr(PEM))
    created = []

    async def create(name):
        created.append(name)
        return f"aijob-{len(created)}"
    monkeypatch.setattr(daily_recheck, "create", create)
    return created


def at(day, hour):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def test_launches_once_per_day_after_the_hour(launcher):
    assert daily_recheck.configured()
    assert asyncio.run(daily_recheck.launch_if_due(at(29, 8))) is None
    first = asyncio.run(daily_recheck.launch_if_due(at(29, 9)))
    assert first == {"name": "speccheck-recheck-2026-10-29", "at": "2026-10-29T09:00:00+00:00", "id": "aijob-1"}
    assert asyncio.run(daily_recheck.launch_if_due(at(29, 23))) is None
    assert asyncio.run(daily_recheck.launch_if_due(at(30, 9)))["name"] == "speccheck-recheck-2026-10-30"
    assert launcher == ["speccheck-recheck-2026-10-29", "speccheck-recheck-2026-10-30"]


def test_a_failed_launch_is_recorded_and_not_retried_that_day(launcher, monkeypatch):
    async def fail(name):
        raise RuntimeError("provider down")
    monkeypatch.setattr(daily_recheck, "create", fail)
    assert asyncio.run(daily_recheck.launch_if_due(at(29, 10)))["error"] == "RuntimeError"
    monkeypatch.setattr(daily_recheck, "create", lambda name: pytest.fail("second launch the same day"))
    assert asyncio.run(daily_recheck.launch_if_due(at(29, 11))) is None


def test_job_request_caps_spend_and_references_keys_only_through_mysterybox(launcher):
    request = daily_recheck.job_request("speccheck-recheck-2026-10-29")
    spec = request.spec
    env = {e.name: e for e in spec.environment_variables}
    assert {k: env[k].value for k in ("SPECCHECK_MODE", "RECHECK_RUNNER", "BUDGET_USD_PER_RUN", "BUDGET_TAVILY_CREDITS_PER_ITEM")} == {
        "SPECCHECK_MODE": "live", "RECHECK_RUNNER": "Nebius Serverless Job speccheck-recheck-2026-10-29",
        "BUDGET_USD_PER_RUN": "0.5", "BUDGET_TAVILY_CREDITS_PER_ITEM": "40"}
    for key in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "ADMIN_TOKEN"):
        assert env[key].mysterybox_secret.secret_id == "mbsec-x" and not env[key].value
    assert "init-judging --usd 0.5 --credits 40" in spec.args and "--post https://speccheck.example" in spec.args
    assert spec.image == settings.speccheck_image and request.metadata.parent_id == "project-x"
    assert "PRIVATE KEY" not in str(request)


def test_only_jobs_this_server_launched_may_sign_a_report(launcher, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", SecretStr(TOKEN))
    headers = {"X-Admin-Token": TOKEN}
    rep = {"checked_at": "2026-10-29T09:30:00+00:00", "mode": "live", "items": [{"id": "c07", "status": "discontinued", "detail": "x"}]}
    for runner in ("Nebius Serverless Job speccheck-recheck-2026-10-29", "Nebius Serverless Job", "nebius job"):
        assert client.post("/api/watch/report", json={**rep, "runner": runner}, headers=headers).status_code == 422
    asyncio.run(daily_recheck.launch_if_due(at(29, 9)))
    ok = client.post("/api/watch/report", json={**rep, "runner": "Nebius Serverless Job speccheck-recheck-2026-10-29"}, headers=headers)
    assert ok.status_code == 200
    assert client.get("/api/watch").json()["runner"] == "Nebius Serverless Job speccheck-recheck-2026-10-29"


def test_not_configured_without_the_service_account_key(launcher, monkeypatch):
    monkeypatch.setattr(settings, "nebius_private_key", SecretStr(""))
    assert not daily_recheck.configured()


def test_create_builds_sdk_credentials_from_the_in_memory_key(launcher, monkeypatch):
    import nebius.api.nebius.ai.v1 as ai
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    monkeypatch.setattr(settings, "nebius_private_key", SecretStr(pem))
    seen = {}

    class Operation:
        resource_id = "aijob-real-shape"

    class FakeJobs:
        def __init__(self, sdk):
            seen["sdk"] = sdk

        async def create(self, request):
            seen["request"] = request
            return Operation()
    monkeypatch.setattr(ai, "JobServiceClient", FakeJobs)
    monkeypatch.setattr(daily_recheck, "create", CREATE)
    assert asyncio.run(daily_recheck.create("speccheck-recheck-2026-10-29")) == "aijob-real-shape"
    assert seen["request"].metadata.name == "speccheck-recheck-2026-10-29"
