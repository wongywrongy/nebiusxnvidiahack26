import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from api import main
from api.config import settings
from api.pipeline.runner import Run, execute
from scripts import smoke


def deployment(*, mode="live", cached=False, replay=False, upload_error=False, bad_watch=False, shared=True):
    calls = []
    def respond(request):
        path = request.url.path
        calls.append((request.method, path, request.content))
        if path == "/api/health":
            body = {"mode": mode, "keys": dict.fromkeys(("NEBIUS_API_KEY", "TAVILY_API_KEY", "ADMIN_TOKEN"), True),
                    "caps": smoke.PRODUCTION_CAPS, "scan_shared_item_budget": shared}
        elif path == "/api/project":
            body = {"mode": mode}
        elif path in ("/api/specs", "/api/scores"):
            body = {}
        elif path == "/api/watch":
            return httpx.Response(404, json={} if bad_watch else {"detail": "No nightly re-check has reported yet"})
        elif path == "/api/inbox":
            body = {"id": "upload-fixture" if request.headers.get("Content-Type") == "application/pdf" else "c01"}
        elif path == "/api/scan":
            body = {"run_id": "smoke-run", "shared_item_budget": True}
        elif path == "/api/runs/smoke-run/results":
            common = {"mode": "live", "validity": "valid", "findings": [{"verdict": "unverified"}], "claims": []}
            body = {"done": True, "results": [{**common, "case_id": "c01", "replayed_from": "recorded" if replay else None,
                "usage": [{"model": "nvidia/nemotron-3-super-120b-a12b", "cached": cached}]}]}
            if not upload_error:
                body["results"].append({**common, "case_id": "upload-fixture"})
        else:
            raise AssertionError(path)
        return httpx.Response(200, json=body)
    return httpx.Client(base_url="https://deployment.test", transport=httpx.MockTransport(respond)), calls


def test_smoke_checks_two_inputs_with_exactly_one_bounded_scan():
    client, calls = deployment()
    with client:
        assert smoke.check(client, poll_s=0) == []
    scans = [json.loads(body) for method, path, body in calls if path == "/api/scan"]
    assert scans == [{"ids": ["c01", "upload-fixture"], "delay_ms": 0, "shared_item_budget": True}]
    assert any(body.startswith(b"%PDF") for _, path, body in calls if path == "/api/inbox")


@pytest.mark.parametrize("options,part", [({"mode": "mock"}, "mode: live"), ({"shared": False}, "shared smoke budget"),
                                        ({"bad_watch": True}, "Watch 404")])
def test_preflight_failures_never_start_paid_work(options, part):
    client, calls = deployment(**options)
    with client:
        assert any(part in f for f in smoke.check(client, poll_s=0))
    assert not any(method == "POST" for method, _, _ in calls)


def test_cached_or_recorded_replay_does_not_establish_fresh_deployment_proof():
    client, _ = deployment(cached=True)
    with client:
        assert any("non-cached" in f for f in smoke.check(client, poll_s=0))
    client, _ = deployment(cached=True, replay=True)
    with client:
        assert any("replayed" in f for f in smoke.check(client, poll_s=0))


def test_read_only_preflight_never_uploads_or_scans():
    client, calls = deployment()
    with client:
        assert smoke.check(client, preflight_only=True) == []
    assert all(method == "GET" for method, _, _ in calls)


def test_failed_upload_run_returns_readable_failure_without_retry():
    client, calls = deployment(upload_error=True)
    with client:
        assert any("upload-fixture: no result" in f for f in smoke.check(client, poll_s=0))
    assert sum(path == "/api/scan" for _, path, _ in calls) == 1


def test_shared_item_credit_allowance_covers_whole_scan(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    monkeypatch.setattr(settings, "budget_tavily_credits_per_item", 5)
    run = asyncio.run(execute(Run(["c01", "c07"], delay_ms=0, shared_item_budget=True)))
    assert len(run.results) == 2
    assert sum(run.ledger.credits.values()) <= 5
    assert any(f.verdict == "unverified" for f in run.results["c07"].findings if f.check == "currency")


def test_health_advertises_caps_and_shared_budget():
    health = TestClient(main.app).get("/api/health").json()
    assert set(smoke.PRODUCTION_CAPS) <= set(health["caps"])
    assert health["scan_shared_item_budget"] is True
