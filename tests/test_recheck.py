"""The nightly re-check (scripts/recheck.py) and the report it posts to the app."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

os.environ.setdefault("SPECCHECK_MODE", "mock")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402
from api.config import settings  # noqa: E402

client = TestClient(main.app)


@pytest.fixture
def runs_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    return tmp_path


def test_recheck_summarizes_the_watched_item(runs_dir):
    import recheck

    assert asyncio.run(recheck.main(["c01", "c07"], post=None)) == 0
    rep = json.loads((runs_dir / "watch" / "latest.json").read_text())
    assert rep["mode"] == "mock" and rep["runner"] == "local" and rep["checked_at"]
    by = {i["id"]: i for i in rep["items"]}
    assert by["c07"]["status"] == "discontinued" and by["c07"]["approved"] == "2024-03-12"
    assert "discontinued" in by["c07"]["quote"].lower() and by["c07"]["source"].startswith("https://")
    assert by["c07"]["replacement"] is None  # No selected driver or cited availability proof.
    assert by["c01"]["status"] == "no_change"
    assert [i["id"] for i in rep["items"]] == ["c07", "c01"]  # worst first
    assert (runs_dir / "watch" / f"{rep['checked_at'][:10]}.json").exists()


def test_project_shows_the_latest_report(runs_dir):
    assert client.get("/api/project").json()["recheck"] is None
    assert client.get("/api/watch").status_code == 404
    rep = {"checked_at": "2026-10-20T07:00:00+00:00", "runner": "Nebius Serverless Job", "mode": "live",
           "items": [{"id": "c07", "status": "discontinued", "detail": "x"}]}
    assert client.post("/api/watch/report", json=rep).status_code == 403  # no admin token set: never accepted
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "admin_token", SecretStr("t-0123456789"))
        assert client.post("/api/watch/report", json=rep, headers={"X-Admin-Token": "wrong"}).status_code == 403
        r = client.post("/api/watch/report", json=rep, headers={"X-Admin-Token": "t-0123456789"})
    assert r.status_code == 200 and r.json()["items"] == 1
    assert client.get("/api/project").json()["recheck"]["runner"] == "Nebius Serverless Job"
    assert client.get("/api/watch").json()["items"][0]["status"] == "discontinued"


def test_recheck_cli_runs_in_mock_mode(runs_dir, monkeypatch):
    env = {**os.environ, "SPECCHECK_MODE": "mock", "RECHECK_RUNNER": "test", "RUNS_DIR": str(runs_dir)}
    r = subprocess.run([sys.executable, "scripts/recheck.py", "--ids", "c07"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "discontinued" in r.stdout and "runner=test" in r.stdout
    assert (runs_dir / "watch" / "latest.json").exists()  # RUNS_DIR is honoured: nothing lands in the repo's runs/
