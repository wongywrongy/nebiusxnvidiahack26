"""Sample tray, inbox and scan (mock mode); recorded samples score against their own expected results."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SPECCHECK_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402
from api.pipeline.cases import all_cases, all_samples, get_case, mock_ready  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402

client = TestClient(main.app)


def test_samples_are_separate_from_the_answer_key_set():
    assert all_samples() and not set(all_samples()) & set(all_cases())
    for sid in all_samples():
        assert get_case(sid)["id"] == sid


def test_project_tray_is_grouped_by_sender():
    p = client.get("/api/project").json()
    tray = {g["from"]: g for g in p["tray"]}
    assert [i["id"] for i in tray["Coastline Firestop"]["items"]] == ["c01", "c02", "c03", "c04"]
    assert [i["id"] for i in tray["Northgate Electric"]["items"]] == ["c06", "s3"]
    assert tray["Coastline Firestop"]["trade"] and tray["Northgate Electric"]["email"]
    items = {i["id"]: i for g in p["tray"] for i in g["items"]}
    assert items["c01"]["ready"] and items["c01"]["received"] and items["c01"]["pages"] > 0
    assert items["s3"]["ready"] == mock_ready(all_samples()["s3"])  # no recording yet: live only
    assert "expected" not in json.dumps(p)  # the answer key stays on the server
    assert [w["id"] for w in p["watched"]] == ["c07"]


def test_inbox_adds_without_running():
    before = set(main.RUNS)
    r = client.post("/api/inbox", json={"id": "c03"})
    assert r.status_code == 200 and r.json()["id"] == "c03" and r.json()["from"] == "Coastline Firestop"
    assert set(main.RUNS) == before
    assert client.post("/api/inbox", json={"id": "c05"}).status_code == 404  # answer-key case, not in the tray
    assert client.post("/api/inbox", json={"id": "s3"}).status_code == 409  # mock mode, no recording


def _wait(run_id, case_id, timeout=10):
    t0 = time.time()
    while (r := client.get(f"/api/runs/{run_id}/results/{case_id}")).status_code != 200:
        assert time.time() - t0 < timeout, case_id
        time.sleep(0.05)
    return r.json()


def test_scan_runs_tray_and_watched_items():
    r = client.post("/api/scan", json={"ids": ["c01", "c03", "c07"], "delay_ms": 0})
    assert r.status_code == 200 and not r.json()["mock"]
    run = r.json()["run_id"]
    assert _wait(run, "c01")["decision"] == "approve" and _wait(run, "c03")["decision"] == "send_back"
    status = next(f for f in _wait(run, "c07")["findings"] if f["check"] == "status")
    assert status["verdict"] == "fail" and status["quote"] and status["evidence"][0]["url"].startswith("https://")
    assert client.post("/api/scan", json={"ids": ["nope"]}).status_code == 400
    assert client.post("/api/scan", json={"ids": []}).status_code == 400
    assert client.post("/api/scan", json={"ids": ["c05"]}).status_code == 400  # not in the tray or watched
    assert client.post("/api/scan", json={"ids": ["s3"]}).status_code == 409


def test_recorded_samples_match_expected():
    ids = sorted(i for i, s in all_samples().items() if mock_ready(s))
    run = asyncio.run(execute(Run(ids, delay_ms=0)))
    for sid in ids:
        assert run.results[sid].decision == all_samples()[sid]["expected"]["decision"], sid
