import json
import os
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import cloud_jobs, main
from api.config import settings


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    binary = tmp_path / "nebius"
    binary.write_bytes((Path(__file__).parent / "fake_nebius.py").read_bytes())
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_NEBIUS_CALLS", str(tmp_path / "calls.jsonl"))
    monkeypatch.setenv("FAKE_NEBIUS_STATE", str(tmp_path / "state"))
    (tmp_path / "state").write_text("fixture-starting")
    for key, value in dict(speccheck_mode="live", runs_dir=tmp_path / "runs", nebius_sa_id="fixture-sa",
                           nebius_public_key_id="fixture-public-id", nebius_project_id="fixture-project",
                           speccheck_image="example.test/speccheck:test", speccheck_url="https://speccheck.test",
                           nebius_evidence_bucket="fixture-bucket").items():
        monkeypatch.setattr(settings, key, value)
    for key in ("nebius_api_key", "tavily_api_key", "admin_token", "nebius_private_key"):
        monkeypatch.setattr(settings, key, SecretStr(f"fixture-only-{key}"))
    for key in ("nebius_api_key", "tavily_api_key", "admin_token"):
        monkeypatch.setattr(settings, f"nebius_secret_{key}", f"fixture-selector-{key}")
    monkeypatch.setattr(settings, "nebius_job_state_map", {"fixture-starting": "starting", "fixture-running": "running",
                                                       "fixture-failure": "failed", "COMPLETED": "done"})
    main._uploads_by_ip.clear()
    with TestClient(main.app) as client:
        client.headers.update({"X-Admin-Token": "fixture-only-admin_token", "Idempotency-Key": "fixture-request"})
        yield client, tmp_path


def test_create_uses_secret_selectors_resource_id_and_never_exposes_pem(cloud, caplog, monkeypatch):
    client, folder = cloud
    monkeypatch.setattr(settings, "model_write", settings.model_triage)
    monkeypatch.setattr(settings, "nebius_base_url", "https://factory.test/v1/")
    assert client.get("/api/project").json()["jobs_available"]
    response = client.post("/api/watch/run")
    assert response.status_code == 200
    job = response.json()
    assert job["id"] == "fixture-job-id" and job["state"] == "queued"
    commands = [json.loads(line) for line in (folder / "calls.jsonl").read_text().splitlines()]
    create = next(c for c in commands if c[:3] == ["ai", "job", "create"])
    assert create.count("--env-secret") == 3
    assert "s3://fixture-bucket:/app/evidence:rw" in create and f"JOB_NAME={job['name']}" in create
    assert "2vcpu-8gb" in create and "32Gi" in create and "--async" in create
    assert not any("fixture-only" in arg for arg in create)
    assert "fixture-only-nebius_private_key" not in caplog.text + response.text + (folder / "runs/watch/jobs.json").read_text()
    repeated = client.post("/api/watch/run")
    assert repeated.json() == job
    assert client.post("/api/watch/run", headers={"Idempotency-Key": "another-request"}).status_code == 409
    assert create.count("--env-secret") == 3
    for name in ("MAX_OUTPUT_TOKENS", "FIX_CREDIT_CAP", "FIX_MAX_CANDIDATES", "MAP_MAX_DEPTH"):
        assert any(arg.startswith(name + "=") for arg in create)
    assert f"MODEL_WRITE={settings.model_triage}" in create and "NEBIUS_BASE_URL=https://factory.test/v1/" in create
    assert all(f"MODEL_{role.upper()}={model}" in create for role, model in settings.models.items())


def test_poll_caches_and_preserves_unknown_states_then_links_report(cloud, monkeypatch):
    client, folder = cloud
    job = client.post("/api/watch/run").json()
    def poll(raw):
        (folder / "state").write_text(raw)
        monkeypatch.setattr(cloud_jobs, "_last_poll", 0)
        return client.get("/api/watch/jobs").json()["jobs"][0]
    assert poll("fixture-starting")["state"] == "starting"
    before = (folder / "calls.jsonl").read_text()
    client.get("/api/watch/jobs")
    assert (folder / "calls.jsonl").read_text() == before
    assert poll("fixture-running")["state"] == "running"
    unknown = poll("OWNER-PASTE-THIS-STATE")
    assert unknown["raw_state"] == "OWNER-PASTE-THIS-STATE" and unknown["state"] == "running" and not unknown["state_known"]
    report = {"checked_at": "2026-10-13T12:00:00Z", "mode": "mock", "runner": "fake CLI", "items": [],
              "job_name": job["name"], "run_id": "test-run", "duration_ms": 1234}
    assert client.post("/api/watch/report", json=report, headers={"X-Admin-Token": "fixture-only-admin_token"}).status_code == 200
    assert poll("COMPLETED")["duration_ms"] == 1234
    assert client.get("/api/watch/jobs").json()["jobs"][0]["state"] == "done"
    assert client.post("/api/watch/run", headers={"Idempotency-Key": "next-request"}).status_code == 429


def test_missing_profile_and_mock_hide_action(cloud, monkeypatch):
    client, _ = cloud
    monkeypatch.setattr(cloud_jobs, "profile_ready", False)
    assert not client.get("/api/project").json()["jobs_available"]
    assert client.post("/api/watch/run").status_code == 409
    monkeypatch.setattr(cloud_jobs, "profile_ready", True)
    monkeypatch.setattr(settings, "speccheck_mode", "mock")
    assert not client.get("/api/watch/jobs").json()["available"]
    assert client.post("/api/watch/run").status_code == 409


def test_missing_secret_selector_cannot_put_raw_key_in_process_arguments(cloud, monkeypatch, caplog):
    client, folder = cloud
    monkeypatch.setattr(settings, "nebius_secret_tavily_api_key", "")
    assert not client.get("/api/project").json()["jobs_available"]
    assert client.post("/api/watch/run").status_code == 409
    with pytest.raises(HTTPException) as error:
        cloud_jobs.command("test")
    assert error.value.status_code == 409
    assert "fixture-only-tavily_api_key" not in caplog.text + str(error.value)
    commands = [json.loads(line) for line in (folder / "calls.jsonl").read_text().splitlines()]
    assert not any(c[:3] == ["ai", "job", "create"] for c in commands)


def test_only_five_jobs_are_kept_and_failed_state_is_configured(cloud, monkeypatch):
    client, _ = cloud
    monkeypatch.setattr(settings, "watch_run_interval_s", 0)
    for n in range(6):
        job = client.post("/api/watch/run", headers={"Idempotency-Key": f"fixture-{n}"}).json()
        cloud_jobs.apply_status(job, {"status": {"state": "fixture-failure"}})
        cloud_jobs.write_jobs([job, *cloud_jobs.read_jobs()[1:]])
    jobs = client.get("/api/watch/jobs").json()["jobs"]
    assert len(jobs) == 5 and all(j["state"] == "failed" for j in jobs)
    assert len(cloud_jobs.read_jobs()) == 6
    assert client.post("/api/watch/run", headers={"Idempotency-Key": "fixture-0"}).json()["name"] == cloud_jobs.read_jobs()[-1]["name"]


def test_public_or_missing_idempotency_request_cannot_launch_cloud_compute(cloud):
    client, folder = cloud
    assert client.post("/api/watch/run", headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert client.post("/api/watch/run", headers={"Idempotency-Key": ""}).status_code == 400
    assert client.post("/api/watch/run", headers={"Idempotency-Key": "unsafe request"}).status_code == 400
    commands = [json.loads(line) for line in (folder / "calls.jsonl").read_text().splitlines()]
    assert not any(c[:3] == ["ai", "job", "create"] for c in commands)
