"""The one-shot launcher follows a real job shape to the end and names the assumption that broke."""

import asyncio
import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import respx
from nebius.api.nebius.ai.v1 import Job, JobStateDetails, JobStatus
from pydantic import SecretStr

from api import daily_recheck
from api.config import settings

spec = importlib.util.spec_from_file_location("launch_recheck", Path(__file__).resolve().parents[1] / "scripts/launch_recheck.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)
URL = "https://speccheck.example"
FOLLOW = launch.follow


@pytest.fixture
def env(monkeypatch):
    for name, value in dict(nebius_sa_id="serviceaccount-x", nebius_public_key_id="publickey-x", nebius_project_id="project-x",
                            speccheck_image="ghcr.io/x/speccheck@sha256:" + "0" * 64, speccheck_url=URL,
                            recheck_mysterybox_secret_id="mbsec-x").items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(settings, "nebius_private_key", SecretStr("synthetic"))
    monkeypatch.setattr(launch.time, "sleep", lambda s: None)
    names = []

    async def create(name):
        names.append(name)
        return "aijob-1"
    monkeypatch.setattr(daily_recheck, "create", create)
    return names


def states(monkeypatch, *seq):
    queue = list(seq)

    class Client:
        async def get(self, request):
            state, code, message = queue.pop(0) if len(queue) > 1 else queue[0]
            return Job(status=JobStatus(state=getattr(JobStatus.State, state),
                                        state_details=JobStateDetails(code=code, message=message)))

    @asynccontextmanager
    async def jobs():
        yield Client()
    monkeypatch.setattr(daily_recheck, "jobs", jobs)


def run():
    return asyncio.run(launch.main())


def test_lists_missing_settings_without_launching(env, monkeypatch, capsys):
    monkeypatch.setattr(settings, "nebius_private_key", SecretStr(""))
    assert run() == 2 and "NEBIUS_PRIVATE_KEY" in capsys.readouterr().out and env == []


@respx.mock
def test_success_needs_completed_state_and_this_jobs_report(env, monkeypatch, capsys):
    states(monkeypatch, ("PROVISIONING", "", ""), ("RUNNING", "", ""), ("COMPLETED", "", ""))
    monkeypatch.setattr(launch, "follow", _follow)
    route = respx.get(f"{URL}/api/watch").mock(side_effect=lambda request: httpx.Response(200, json={
        "runner": daily_recheck.PREFIX + env[0], "checked_at": "2026-10-28T23:00:00+00:00",
        "items": [{"id": "c07", "status": "discontinued"}]}))
    assert run() == 0
    out = capsys.readouterr().out
    assert "PROVISIONING" in out and "COMPLETED" in out and "c07 discontinued" in out and route.called
    assert env[0].startswith("speccheck-recheck-manual-")


def _follow(job_id):
    return FOLLOW(job_id, poll_s=0)


@respx.mock
def test_secret_permission_failure_names_the_role(env, monkeypatch, capsys):
    states(monkeypatch, ("FAILED", "SecretAccessDenied", "permission denied reading mysterybox secret mbsec-x"))
    monkeypatch.setattr(launch, "follow", _follow)
    assert run() == 1
    assert "Role: the service account cannot read the MysteryBox payload" in capsys.readouterr().out


@respx.mock
def test_completed_without_a_report_points_at_network_or_token(env, monkeypatch, capsys):
    states(monkeypatch, ("COMPLETED", "", ""))
    monkeypatch.setattr(launch, "follow", _follow)
    respx.get(f"{URL}/api/watch").mock(return_value=httpx.Response(404, json={}))
    assert run() == 1
    assert "Network or admin token" in capsys.readouterr().out


def test_create_failures_map_to_assumptions():
    assert launch.create_failure("PERMISSION_DENIED", "").startswith("Role:")
    assert launch.create_failure("UNAUTHENTICATED", "").startswith("Key:")
    assert launch.create_failure("UNAVAILABLE", "").startswith("Network:")
    assert launch.create_failure("NOT_FOUND", "secret").startswith("Naming:")
    assert launch.job_failure("FAILED", "payload key NEBIUS_API_KEY not found in secret").startswith("Env var naming:")
    assert launch.job_failure("ERROR", "failed to pull image manifest").startswith("Network:")
