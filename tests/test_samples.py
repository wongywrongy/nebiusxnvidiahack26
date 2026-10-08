"""Sample inbox: listed in the project, sendable, and scored against their own expected results (mock mode)."""

import asyncio
import os
import sys
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


def test_project_lists_samples_with_readiness():
    samples = {s["id"]: s for s in client.get("/api/project").json()["samples"]}
    assert set(samples) == set(all_samples())
    for sid, s in samples.items():
        assert s["url"].startswith("https://") and s["subject"] and s["hint"]
        assert s["ready"] == mock_ready(all_samples()[sid])


def test_send_sample():
    ready = next(i for i, s in all_samples().items() if mock_ready(s))
    r = client.post(f"/api/samples/{ready}?delay_ms=0")
    assert r.status_code == 200 and r.json()["case"]["id"] == ready and r.json()["case"]["number"]
    unrecorded = [i for i, s in all_samples().items() if not mock_ready(s)]
    if unrecorded:
        assert client.post(f"/api/samples/{unrecorded[0]}").status_code == 409
    assert client.post("/api/samples/nope").status_code == 404


def test_recorded_samples_match_expected():
    ids = sorted(i for i, s in all_samples().items() if mock_ready(s))
    run = asyncio.run(execute(Run(ids, delay_ms=0)))
    for sid in ids:
        assert run.results[sid].decision == all_samples()[sid]["expected"]["decision"], sid
