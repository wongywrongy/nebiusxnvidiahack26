"""Judge playground: isolated storage and mocked providers, never paid calls."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr
import pytest
import respx

from api import main
from api.config import ROOT, settings
from api.pipeline import checklists, runner
from api.pipeline.cases import get_upload, save_upload
from api.pipeline.decide import decide
from api.pipeline.spec_check import check
from api.schemas import Claim, Requirement, UploadChecklist

DATA = Path(__file__).parent / "data"


@pytest.fixture
def playground(tmp_path, monkeypatch):
    for name, suffix in (("raw_dir", "raw"), ("uploads_dir", "raw/uploads"), ("data_dir", "project"),
                         ("runs_dir", "runs"), ("cache_dir", "cache"), ("fixtures_dir", "fixtures")):
        monkeypatch.setattr(settings, name, tmp_path / suffix)
    settings.fixtures_dir.mkdir()
    monkeypatch.setattr(settings, "nebius_api_key", SecretStr("test-playground-model"))
    monkeypatch.setattr(settings, "tavily_api_key", SecretStr("test-playground-web"))
    monkeypatch.setattr(main, "RUNS", {})
    main._uploads_by_ip.clear()
    return TestClient(main.app)


def body():
    return json.loads((DATA / "upload-checklist.json").read_text())


def upload(client):
    response = client.post("/api/inbox?name=hardware.pdf", content=(DATA / "off-topic.pdf").read_bytes())
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("fault", ["bad-section", "empty", "too-many", "duplicate", "mismatched", "blank-title", "long-title"])
def test_checklist_validation(playground, fault):
    data = body()
    if fault == "bad-section":
        data["section"] = "../08_71_00"
    elif fault == "empty":
        data["requirements"] = []
    elif fault == "too-many":
        data["requirements"] = [{**data["requirements"][0], "id": str(n)} for n in range(31)]
    elif fault == "duplicate":
        data["requirements"][1]["id"] = data["requirements"][0]["id"]
    elif fault == "mismatched":
        data["requirements"][1]["section"] = "07 84 00"
    else:
        data["title"] = " " if fault == "blank-title" else "x" * 161
    response = playground.post("/api/checklists", json=data)
    assert response.status_code == 422
    assert not settings.uploads_dir.exists()
    assert not settings.data_dir.exists()


def test_save_is_unreviewed_upload_only_and_shares_upload_rate_limit(playground, monkeypatch):
    data = {**body(), "reviewed_at": "2026-10-27"}
    monkeypatch.setattr(settings, "uploads_per_ip_per_hour", 1)
    response = playground.post("/api/checklists", json=data)
    assert response.status_code == 200
    saved = response.json()
    assert saved == {"id": saved["id"], "section": "08 71 00", "title": "Door Hardware", "n": 2}
    path = settings.uploads_dir / "checklists" / f"{saved['id']}.json"
    stored = json.loads(path.read_text())
    assert stored["created_at"] and stored["checklist"]["reviewed_at"] is None
    assert not settings.data_dir.exists()
    assert playground.post("/api/inbox", content=(DATA / "off-topic.pdf").read_bytes()).status_code == 429


def test_spec_patch_persists_rejects_tray_and_locks_when_scanning(playground, monkeypatch):
    case = upload(playground)
    identifier = case["id"]
    for invalid in ({}, {"spec": "09 91 00"}, {"spec": "07 84 00", "checklist_id": "ignored"}):
        assert playground.patch(f"/api/inbox/{identifier}", json=invalid).status_code == 422
    assert playground.patch("/api/inbox/c01", json={"spec": "26 51 00"}).status_code == 422
    assert playground.post("/api/inbox", json={"id": "c01", "checklist_id": "ck-abc"}).status_code == 422
    response = playground.patch(f"/api/inbox/{identifier}", json={"spec": "26 51 00"})
    assert response.status_code == 200 and response.json()["section"] == "26 51 00"
    assert get_upload(identifier)["section"] == "26 51 00"
    pending = []
    monkeypatch.setattr(settings, "data_dir", ROOT / "data")
    monkeypatch.setattr(main, "_spawn", pending.append)
    try:
        assert playground.post("/api/scan", json={"ids": [identifier]}).status_code == 200
        assert get_upload(identifier)["scanned_at"]
        assert playground.patch(f"/api/inbox/{identifier}", json={"spec": "07 84 00"}).status_code == 409
    finally:
        for coro in pending:
            coro.close()


def test_draft_assignment_and_expired_scan_are_clear_404s(playground):
    case = upload(playground)
    saved = playground.post("/api/checklists", json=body()).json()
    response = playground.patch(f"/api/inbox/{case['id']}", json={"spec": saved["id"]})
    assert response.status_code == 200 and response.json()["checklist_id"] == saved["id"]
    assert get_upload(case["id"])["section"] == "08 71 00"
    path = settings.uploads_dir / "checklists" / f"{saved['id']}.json"
    stored = json.loads(path.read_text())
    stored["created_at"] = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    path.write_text(json.dumps(stored))
    response = playground.post("/api/scan", json={"ids": [case["id"]]})
    assert response.status_code == 404 and "expired" in response.json()["detail"]
    assert not main.RUNS
    assert playground.patch(f"/api/inbox/{case['id']}", json={"spec": "ck-" + "0" * 32}).status_code == 404
    checklists.prune_uploads()
    assert not path.exists()
    assert playground.patch(f"/api/inbox/{case['id']}", json={"spec": "07 84 00"}).status_code == 200
    assert "checklist_id" not in get_upload(case["id"])


@pytest.mark.parametrize("minimum,decision", [(200000, "approve_with_note"), (400000, "send_back")])
@pytest.mark.parametrize("mode", ["mock", "live"])
def test_runner_uses_saved_fixture_checklist_without_project_rules(playground, monkeypatch, minimum, decision, mode):
    case = upload(playground)
    checklist = body()
    checklist["requirements"][0]["value"] = minimum
    saved = playground.post("/api/checklists", json=checklist).json()
    playground.patch(f"/api/inbox/{case['id']}", json={"spec": saved["id"]})
    stored_case = get_upload(case["id"])
    stored_case.update(fixture="hardware", conditions=[{"invalid": "must not be used"}],
                       not_applicable=["cycles"], manufacturer_domains=["wrong.test"])
    save_upload(stored_case)
    fixture = {"claims": {"product": "Harbor X1", "manufacturer": "Harbor", "model": "Harbor X1", "claims": [
        {"id": "cycle-claim", "product": "Harbor X1", "manufacturer": "Harbor", "property": "cycles", "value": 300000,
         "unit": "cycles", "page": 1, "quote": "Tested for 300000 cycles.",
         "scope": "product_wide", "scope_quote": "Tested for 300000 cycles."}]}}
    (settings.fixtures_dir / "hardware.json").write_text(json.dumps(fixture))
    (settings.fixtures_dir / "fix").mkdir()
    (settings.fixtures_dir / "fix/hardware.json").write_text("{}")
    async def forbidden(*args):
        pytest.fail("An upload draft must not read the reviewed checklist or source spec")
    monkeypatch.setattr(runner.extract, "requirements_for", forbidden)
    monkeypatch.setattr(runner, "load_spec_text", forbidden)
    original = runner.verify.verify
    async def verify(case, *args, **kwargs):
        assert case["manufacturer_domains"] == [] and case["conditions"] == [] and case["not_applicable"] == []
        return await original(case, *args, **kwargs)
    monkeypatch.setattr(runner.verify, "verify", verify)
    monkeypatch.setattr(settings, "data_dir", ROOT / "data")
    monkeypatch.setattr(settings, "speccheck_mode", mode)
    def reply(request):
        data = json.loads(request.content)
        if "tools" in data:
            assert "response_format" not in data
            message = {"tool_calls": [{"id": "done", "function": {"name": "finish", "arguments": json.dumps(
                {"found": False, "status": "unknown", "note": "Synthetic test: no current sources found."})}}]}
        else:
            name = data["response_format"]["json_schema"]["name"]
            payload = {"TriageOut": {"pages": [{"page": 1, "kind": "product_data"}]}, "ClaimsRead": fixture["claims"],
                       "SourceRead": {"status": "unknown", "current_values": []},
                       "ReportOut": {"summary": "Synthetic test review.", "note_to_subcontractor": ""}}[name]
            message = {"content": json.dumps(payload)}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": message}],
                                        "usage": {"prompt_tokens": 20, "completion_tokens": 20}})
    with respx.mock as http:
        if mode == "live":
            model = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=reply)
            search = http.post("https://api.tavily.com/search").mock(return_value=httpx.Response(
                200, json={"results": [], "usage": {"credits": 1}}))
        run = asyncio.run(runner.execute(runner.Run([case["id"]], delay_ms=0)))
        if mode == "live":
            assert model.calls and search.calls
            assert all(not json.loads(call.request.content).get("include_domains") for call in search.calls)
        else:
            assert not http.calls
    result = run.results[case["id"]]
    assert result.mode == mode and result.decision == decision
    assert result.checklist_id == saved["id"] and result.spec_title == "Door Hardware"
    assert result.spec_rule_count == 2 and result.spec_match_count == 1
    assert result.findings[0].verdict == ("fail" if decision == "send_back" else "pass")
    assert result.findings[0].spec_ref == "08 71 00 2.1.A"
    assert {f.requirement_id for f in result.findings if f.requirement_id} == {"cycles", "grade"}
    if decision == "send_back":
        fix = result.findings[0].fix
        assert fix and "firestop" not in fix.query.lower() and "400000 cycles" in fix.query


def test_off_topic_live_upload_skips_every_web_and_fix_call(playground, monkeypatch):
    case = upload(playground)
    monkeypatch.setattr(settings, "data_dir", ROOT / "data")
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    def reply(request):
        name = json.loads(request.content)["response_format"]["json_schema"]["name"]
        payload = {"TriageOut": {"pages": [{"page": 1, "kind": "product_data"}]},
                   "RequirementsOut": {"requirements": [{**body()["requirements"][0], "section": "07 84 00", "property": "voc_g_per_l"}]},
                   "ClaimsRead": {"product": "Harbor X1", "manufacturer": "Harbor", "claims": []},
                   "ReportOut": {"summary": "No values match this section.", "note_to_subcontractor": ""}}[name]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}],
                                        "usage": {"prompt_tokens": 20, "completion_tokens": 20}})
    with respx.mock as http:
        model = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=reply)
        run = asyncio.run(runner.execute(runner.Run([case["id"]], delay_ms=0)))
        assert len(http.calls) == len(model.calls) == 3
    result = run.results[case["id"]]
    assert result.decision == "not_applicable" and result.web_credits == result.fresh_web_credits == 0
    n = len(json.loads((settings.data_dir / "requirements/07_84_00.json").read_text())["requirements"])
    assert result.spec_match_count == 0 and result.spec_rule_count == n
    assert not {"verify", "investigate", "fix"} & {e.stage for e in run.events}
    assert f"0 of {n} rules matched" in next(e.message for e in run.events if e.stage == "spec_check")
    assert not result.note_to_subcontractor and not any(f.fix for f in result.findings)


def test_incomparable_quoted_value_is_uncertain_not_off_topic():
    requirement = Requirement.model_validate(body()["requirements"][0])
    claim = Claim(id="c", product="Harbor X1", manufacturer="Harbor", property="cycles", value="varies",
                  page=1, quote="Cycle rating varies by configuration.")
    findings = check([requirement], [claim])
    assert findings[0].verdict == "unverified" and decide(findings) == "approve_with_note"


def test_tray_with_no_matched_claims_still_checks_the_manufacturer(playground, monkeypatch):
    from api.schemas import ClaimsOut
    monkeypatch.setattr(settings, "data_dir", ROOT / "data")
    monkeypatch.setattr(settings, "fixtures_dir", ROOT / "data/fixtures")
    calls = []
    async def no_claims(*args, **kwargs):
        return ClaimsOut(product="Synthetic unmatched tray document", manufacturer="", claims=[]), []
    async def verify(case, *args, **kwargs):
        calls.append(case["id"])
        return [runner.verify.unconfirmed("Synthetic missing manufacturer evidence")], [], [], 0, None
    monkeypatch.setattr(runner.extract, "extract_claims", no_claims)
    monkeypatch.setattr(runner.verify, "verify", verify)
    run = asyncio.run(runner.execute(runner.Run(["c01"], delay_ms=0)))
    assert calls == ["c01"] and any(e.stage == "verify" for e in run.events)
    assert run.results["c01"].spec_match_count == 0
    assert run.results["c01"].decision != "not_applicable"


def test_runner_refuses_a_tray_checklist_even_without_the_api(playground, monkeypatch):
    case = {**upload(playground), "upload": False, "fixture": None, "checklist_id": "ck-" + "0" * 32}
    monkeypatch.setattr(settings, "data_dir", ROOT / "data")
    run = asyncio.run(runner.execute(runner.Run([case["id"]], delay_ms=0, catalog={case["id"]: case})))
    assert not run.results
    assert any(e.stage == "error" and "only be used for uploaded PDFs" in e.message for e in run.events)


def test_try_catalog_exposes_links_without_adding_scoring_cases(playground, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", ROOT / "data")
    project = playground.get("/api/project").json()
    examples = project["try"]
    assert examples == playground.get("/api/specs").json()["try"]
    assert len([e for e in examples if e["kind"] == "product"]) in (4, 5)
    assert len([e for e in examples if e["kind"] == "spec"]) == 1
    assert all(set(e) == {"title", "kind", "url", "fits"} and e["url"].startswith("https://") for e in examples)
    assert any(e["fits"].startswith("pair with ") for e in examples)
