"""Fix step, uploads and the scores endpoint, all in mock mode."""

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("SPECCHECK_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402
from api.config import settings  # noqa: E402
from api.pipeline import fix  # noqa: E402
from api.pipeline.cases import all_cases  # noqa: E402
from api.pipeline.runner import Run, execute, replay  # noqa: E402

client = TestClient(main.app)
SEND_BACK = sorted(c for c, v in all_cases().items() if v["expected"]["decision"] == "send_back")


@pytest.fixture(scope="module")
def run():
    return asyncio.run(execute(Run(sorted(all_cases()), delay_ms=0)))


def fixes(result):
    return [f.fix for f in result.findings if f.fix]


def test_fix_only_on_send_backs(run):
    for cid, res in run.results.items():
        assert bool(fixes(res)) == (cid in SEND_BACK), cid
        assert ("fix" in {e.stage for e in run.events if e.case_id == cid}) == (cid in SEND_BACK), cid


def test_passes_only_with_every_check_passed(run):
    for cid in SEND_BACK:
        (f,) = fixes(run.results[cid])
        assert len(f.candidates) <= settings.fix_max_candidates
        for c in f.candidates:
            assert c.passes == (bool(c.checks) and all(k.ok is True for k in c.checks)), (cid, c.name)
        best = next((c for c in f.candidates if c.passes), None)
        assert f.suggest == (best.name if best else ""), cid
        if not best:
            assert f.head == "No passing replacement found", cid


def test_c04_sti_fails_on_t_rating(run):
    (f,) = fixes(run.results["c04"])
    sti = next(c for c in f.candidates if "W-L-1079" in c.name)
    assert not sti.passes and sti.source_url
    t = next(k for k in sti.checks if k.label == "Temperature rating (T)")
    assert t.ok is False and t.note == "T 0 hr"
    assert f.head == "No passing replacement found" and not f.suggest


def test_fix_names_the_current_documents(run):
    assert "Rev B" in fixes(run.results["c03"])[0].suggest
    assert "BLT 2x4" in fixes(run.results["c07"])[0].suggest
    c06 = fixes(run.results["c06"])[0]  # the 2025 sheet doesn't state CRI, dimming, warranty or DLC
    assert not c06.suggest and "04/11/25" in c06.candidates[0].name


def test_fix_respects_the_credit_cap(run):
    res = run.results["c04"]
    from api.pipeline.cases import get_case
    from api.schemas import ClaimsOut, Requirement

    case = get_case("c04")
    findings = [f.model_copy(deep=True) for f in res.findings]
    for f in findings:
        f.fix = None
    claims = ClaimsOut(product="W-L-2078", manufacturer="Hilti", claims=res.claims)
    reqs = [Requirement(**c) for c in case["conditions"]] + [
        Requirement(id="fs-t-eq-f", section="07 84 00", paragraph="", property="t_rating_hr", operator="eq_ref",
                    value="f_rating_hr", text="T rating must equal the F rating", severity="critical")]
    _, credits = asyncio.run(fix.find_fixes(case, reqs, claims, findings, max_candidates=3, credit_cap=4))
    got = next(f.fix for f in findings if f.fix)
    assert credits <= 4
    assert not got.candidates and got.query  # no credits left to verify a candidate; the search is still shown


@pytest.fixture
def cleanup():
    """Upload ids a test created; their folders under data/raw/uploads are removed afterwards."""

    ids: list[str] = []
    yield ids
    for i in ids:
        shutil.rmtree(settings.uploads_dir / i, ignore_errors=True)


def _pdf(cid):
    return settings.raw_dir / all_cases()[cid]["submittal"][0]["file"]


def _upload_and_scan(body, name):
    """Add a PDF to the inbox (no run), then scan it. Returns (public case, scan response)."""
    case = client.post(f"/api/inbox?name={name}", content=body, headers={"content-type": "application/pdf"}).json()
    return case, client.post("/api/scan", json={"ids": [case["id"]], "delay_ms": 0}).json()


def _wait_result(run_id, case_id, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/runs/{run_id}/results/{case_id}")
        if r.status_code == 200:
            return r.json()
        time.sleep(0.05)
    raise AssertionError("upload run did not finish")


@pytest.mark.skipif(not _pdf("c03").exists(), reason="run scripts/fetch_docs.py to download the PDFs")
def test_upload_of_a_known_pdf_runs_like_its_case(cleanup):
    case, scan = _upload_and_scan(_pdf("c03").read_bytes(), "IC 15WB.pdf")
    cleanup.append(case["id"])
    assert case["upload"] and case["mock_fixture"] == "c03" and case["section"] == "07 84 00" and case["pages"] == 4
    res = _wait_result(scan["run_id"], case["id"])
    assert res["decision"] == "send_back"
    assert any(f.get("fix") for f in res["findings"])
    pages = client.get(f"/api/docs/{case['id']}/{case['submittal'][0]['file'].rsplit('/', 1)[-1]}/pages").json()
    assert pages["count"] == 4


def test_upload_rejects_non_pdf_and_unknown_pdf_runs_on_defaults(cleanup):
    assert client.post("/api/inbox?name=x.pdf", content=b"hello").status_code == 400
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "LED troffer 4000 lumens, luminaire data")
    case, scan = _upload_and_scan(doc.tobytes(), "mine.pdf")
    cleanup.append(case["id"])
    assert case["mock_fixture"] is None and case["section"] == "26 51 00"
    res = _wait_result(scan["run_id"], case["id"])
    assert res["decision"] == "approve_with_note"  # nothing could be read in mock mode: everything is "not stated"
    assert "Mock mode" in res["summary"]


def test_scores_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "scores_file", tmp_path / "scores.json")
    monkeypatch.setattr(settings, "recorded_dir", tmp_path / "recorded")
    assert client.get("/api/scores").status_code == 404
    settings.scores_file.write_text(json.dumps({"right_call": {"n": 8, "of": 8}}))
    assert client.get("/api/scores").json()["right_call"]["n"] == 8


def test_run_scoring_set_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "scores_file", tmp_path / "scores.json")
    s = client.post("/api/scores/run").json()
    assert s["right_call"] == {"n": 8, "of": 8} and s["false_alarms"]["n"] == 0
    assert json.loads((tmp_path / "scores.json").read_text())["run_id"] == s["run_id"]


def test_recorded_run_is_the_public_demo(run, tmp_path, monkeypatch):
    """Only a recording on disk, as in the container: health names it, it backs scores, results and replay."""
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "recorded_dir", tmp_path / "recorded")
    monkeypatch.setattr(settings, "scores_file", tmp_path / "runs" / "scores.json")
    rec = settings.recorded_dir / run.id
    shutil.copytree(run.dir, rec)
    (rec / "scores.json").write_text(json.dumps({"run_id": run.id}))

    assert client.get("/api/health").json()["recorded"] == run.id
    assert client.get("/api/scores").json()["run_id"] == run.id
    assert len(client.get(f"/api/runs/{run.id}/results").json()["results"]) == len(run.results)
    assert client.get("/api/runs/..%2Frecorded/results").status_code == 404
    assert client.post("/api/runs/replay", json={"source_run_id": f"../recorded/{run.id}"}).status_code == 404

    again = asyncio.run(replay(Run([]), run.id, speed=1e6))
    assert {c: r.decision for c, r in again.results.items()} == {c: r.decision for c, r in run.results.items()}
