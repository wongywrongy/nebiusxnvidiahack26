"""Public scans and failure recovery: fixtures and intercepted HTTP only, no provider spend."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import main
from api.config import settings
from api.pipeline import decide, extract, fix, verify
from api.pipeline.runner import Run, execute
from api.providers import ProviderError, RateLimited, budget


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    for name, suffix in (("runs_dir", "runs"), ("recorded_dir", "recorded"), ("cache_dir", "cache"),
                         ("uploads_dir", "uploads")):
        monkeypatch.setattr(settings, name, tmp_path / suffix)
    main._uploads_by_ip.clear()
    monkeypatch.setattr(main, "RUNS", {})
    return TestClient(main.app)


def defer(monkeypatch):
    pending = []
    monkeypatch.setattr(main, "_spawn", pending.append)
    return pending


def test_explicit_fresh_recheck_cannot_fall_back_to_replay(isolated, monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "budget_usd_per_day", 0)
    response = isolated.post("/api/scan", json={"ids": ["c01"], "refresh_web": True})
    assert response.status_code == 429 and "fresh re-check cannot use replay" in response.json()["detail"]


@pytest.mark.parametrize("cap", ["budget_usd_per_day", "budget_tavily_credits_per_day"])
def test_spent_budget_replays_only_requested_recorded_items(isolated, monkeypatch, cap):
    # This temporary recording is made from fixtures; it is never published as a live result.
    source = asyncio.run(execute(Run(["c01", "c02"], delay_ms=0)))
    before = (source.dir / "results/c01.json").read_text()
    settings.recorded_dir.mkdir()
    source.dir.rename(settings.recorded_dir / source.id)
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, cap, 0)
    pending = defer(monkeypatch)
    response = isolated.post("/api/scan", json={"ids": ["c01"]})
    assert response.status_code == 200
    body = response.json()
    assert body["replay_of"] == source.id
    assert "today's live budget is spent" in body["note"]
    assert f"{source.id[:4]}-{source.id[4:6]}-{source.id[6:8]}" in body["note"]
    run = asyncio.run(pending.pop())
    assert set(run.results) == {"c01"} and run.done.is_set()
    assert {e.case_id for e in run.events} == {"c01"}
    assert run.results["c01"].replayed_from == source.id
    assert (settings.recorded_dir / source.id / "results/c01.json").read_text() == before
    assert "replayed_from" in isolated.get(f"/api/runs/{run.id}/results/c01").json()
    h = isolated.get("/api/health").json()
    assert 0 in h["budget"].values()


def test_spent_budget_refuses_uploads_and_missing_recordings(isolated, monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "budget_usd_per_day", 0)
    monkeypatch.setattr(main, "_scannable", lambda i: {"upload": i == "upload-test"})
    for ids in (["upload-test"], ["c01"]):
        response = isolated.post("/api/scan", json={"ids": ids})
        assert response.status_code == 429 and "budget is spent" in response.json()["detail"]
    assert isolated.post("/api/inbox", content=b"%PDF").status_code == 429
    assert not main.RUNS


def test_public_upload_is_live_by_default_with_rate_limit_and_admin_bypass(isolated, monkeypatch):
    assert settings.public_uploads_live
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "admin_token", SecretStr("test-admin"))
    monkeypatch.setattr(settings, "uploads_per_ip_per_hour", 1)
    monkeypatch.setattr(main, "_scannable", lambda i: {"upload": True})
    pending = defer(monkeypatch)
    try:
        public = isolated.post("/api/scan", json={"ids": ["upload-test"]})
        assert public.status_code == 200 and public.json()["mock"] == []
        assert not main.RUNS[public.json()["run_id"]].mock
        assert isolated.post("/api/scan", json={"ids": ["upload-test"]}).status_code == 429
        admin = isolated.post("/api/scan", json={"ids": ["upload-test"]}, headers={"X-Admin-Token": "test-admin"})
        assert admin.status_code == 200 and admin.json()["mock"] == []
    finally:
        for task in pending:
            task.close()


@pytest.mark.parametrize("stage,error,reason", [
    ("triage", RateLimited("Token Factory rate limit (429)"), "Token Factory rate limit; try again in a minute"),
    ("extract_claims", ProviderError("extract: reply hit MAX_OUTPUT_TOKENS (8192)"), "The reply was cut off at the token limit"),
])
def test_early_stage_error_reason_reaches_event_stream(isolated, monkeypatch, stage, error, reason):
    async def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(extract, stage, fail)
    run = asyncio.run(execute(Run(["c01"], delay_ms=0)))
    event = next(e for e in run.events if e.stage == "error")
    assert event.message == reason and event.data == {"reason": reason}
    assert not run.results
    body = isolated.get(f"/api/runs/{run.id}/events").text
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert any(e.get("message") == reason and e["data"]["reason"] == reason for e in events)


@pytest.mark.parametrize("module,function,case", [(verify, "verify", "c01"), (fix, "find_fixes", "c03"), (decide, "report", "c01")])
def test_later_provider_failures_keep_result_with_unconfirmed_explanation(isolated, monkeypatch, module, function, case):
    async def fail(*args, **kwargs):
        raise ProviderError("Token Factory unavailable; sensitive response")
    monkeypatch.setattr(module, function, fail)
    run = asyncio.run(execute(Run([case], delay_ms=0)))
    assert not any(e.stage == "error" for e in run.events)
    result = run.results[case]
    if module is verify:
        finding = next(f for f in result.findings if f.check == "currency")
        assert finding.verdict == "unverified" and "could not complete" in finding.detail
    else:
        assert "could not complete" in result.warnings[0]
    assert "sensitive response" not in result.model_dump_json()


def test_replay_rejects_zero_speed(isolated):
    assert isolated.post("/api/runs/replay", json={"source_run_id": "x", "speed": 0}).status_code == 422


def test_remaining_budget_clamps_overage(isolated, monkeypatch):
    monkeypatch.setattr(budget, "today", lambda: {
        "usd": settings.budget_usd_per_day + 1,
        "credits": settings.budget_tavily_credits_per_day + 1,
    })
    assert budget.remaining() == {"usd_left": 0, "credits_left": 0}
