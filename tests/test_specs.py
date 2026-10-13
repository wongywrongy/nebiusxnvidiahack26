"""Checklist previews never become project rules without an authenticated, dated review."""

import asyncio
import json

import httpx
import pymupdf
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import main
from api.config import settings
from api.pipeline.extract import checklist_path, requirements_for

SECTION = "07 84 00"
REQ = {"id": "voc", "section": SECTION, "paragraph": "2.1.B", "property": "voc_g_per_l",
       "operator": "lte", "value": 250, "unit": "g/L", "text": "VOC limit 250 g/L", "severity": "major"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "admin_token", SecretStr("reviewer-test-token"))
    main._uploads_by_ip.clear()
    return TestClient(main.app)


def pdf():
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "07 84 00 Firestopping. 2.1.B VOC limit 250 g/L.")
        return doc.tobytes()


def model_reply():
    return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps({"requirements": [REQ]})}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 100}})


def test_specs_expose_fixture_provenance_without_inventing_dates(client):
    body = client.get("/api/specs").json()
    assert len(body["sections"]) == 2 and body["mode"] == "mock"
    for spec in body["sections"]:
        assert spec["status"] == "fixture" and spec["used_by_scans"] == "mock"
        assert spec["source_url"].startswith("https://") and spec["control_version"]
        assert "Mock-mode stand-in" in spec["note"]
        assert spec["checklist"]["drafted_at"] is None and spec["checklist"]["reviewed_at"] is None
        assert spec["checklist"]["requirements"]


def test_mock_drafting_is_live_only(client):
    response = client.post("/api/specs/draft", params={"section": SECTION}, content=pdf())
    assert response.status_code == 409 and "Live only" in response.json()["detail"]


def test_legacy_saved_checklist_does_not_invent_a_review(client):
    path = checklist_path(SECTION)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"requirements": [REQ]}))
    section = client.get("/api/specs").json()["sections"][0]
    assert section["status"] == "saved" and section["checklist"]["reviewed_at"] is None


@respx.mock
def test_live_draft_has_provenance_uses_cache_and_never_saves_checklist(client, monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    route = respx.post(settings.nebius_base_url + "chat/completions").mock(return_value=model_reply())
    data = pdf()
    response = client.post("/api/specs/draft", params={"section": SECTION, "name": "project.pdf"}, content=data)
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["drafted_by"] == settings.model_extract
    assert draft["source_name"] == "project.pdf" and draft["source_sha256"]
    assert draft["drafted_at"] and draft["reviewed_at"] is None
    assert draft["requirements"][0]["paragraph"] == "2.1.B"
    assert not settings.data_dir.exists()
    cached = client.post("/api/specs/draft", params={"section": SECTION}, content=data)
    assert cached.json()["usage"]["cached"] and len(route.calls) == 1
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == settings.model_extract and "250 g/L" in str(body["messages"])


@pytest.mark.parametrize("kind", ["daily", "run", "rate", "size", "invalid"])
def test_draft_limits_stop_before_provider(client, monkeypatch, kind):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    expected = 429
    if kind == "daily": monkeypatch.setattr(settings, "budget_usd_per_day", 0)
    if kind == "run": monkeypatch.setattr(settings, "budget_usd_per_run", 0)
    if kind == "rate": monkeypatch.setattr(settings, "uploads_per_ip_per_hour", 0)
    if kind == "size":
        monkeypatch.setattr(settings, "max_upload_mb", 0)
        expected = 413
    if kind == "invalid": expected = 400
    response = client.post("/api/specs/draft", params={"section": SECTION}, content=b"not a PDF" if kind == "invalid" else pdf())
    assert response.status_code == expected
    assert not checklist_path(SECTION).exists()


@respx.mock
def test_draft_provider_failure_is_plain_and_does_not_persist(client, monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    respx.post(settings.nebius_base_url + "chat/completions").mock(return_value=httpx.Response(503, text="sensitive provider body"))
    response = client.post("/api/specs/draft", params={"section": SECTION}, content=pdf())
    assert response.status_code == 503
    assert "could not complete" in response.json()["detail"] and "sensitive" not in response.text
    assert not checklist_path(SECTION).exists()


def test_only_admin_reviewed_checklists_are_saved_and_used_live(client, monkeypatch):
    body = {"requirements": [REQ], "drafted_by": settings.model_extract, "source_name": "project.pdf",
            "drafted_at": "2026-10-13T00:00:00Z", "reviewed_at": "2026-10-13"}
    assert client.post(f"/api/specs/{SECTION}", json=body).status_code == 403
    headers = {"X-Admin-Token": "reviewer-test-token"}
    missing_date = {**body, "reviewed_at": None}
    assert client.post(f"/api/specs/{SECTION}", json=missing_date, headers=headers).status_code == 422
    assert client.post("/api/specs/unknown", json=body, headers=headers).status_code == 404
    wrong = {**body, "requirements": [{**REQ, "section": "26 51 00"}]}
    assert client.post(f"/api/specs/{SECTION}", json=wrong, headers=headers).status_code == 422
    assert client.post(f"/api/specs/{SECTION}", json={**body, "requirements": [REQ, REQ]}, headers=headers).status_code == 422
    assert client.post(f"/api/specs/{SECTION}", json=body, headers=headers).status_code == 200
    saved = json.loads(checklist_path(SECTION).read_text())
    assert saved["reviewed_at"] == "2026-10-13" and saved["drafted_by"] == settings.model_extract
    section = client.get("/api/specs").json()["sections"][0]
    assert section["status"] == "reviewed" and section["checklist"] == saved
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    out, usage = asyncio.run(requirements_for(SECTION, ""))
    assert usage is None and out.requirements[0].id == "voc"


@respx.mock
def test_new_section_draft_is_transient_but_admin_cannot_save_it(client, monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    route = respx.post(settings.nebius_base_url + "chat/completions").mock(return_value=model_reply())
    response = client.post("/api/specs/draft", params={"section": "09 91 00", "title": "Painting"}, content=pdf())
    assert response.status_code == 200
    assert response.json()["draft"]["title"] == "Painting"
    assert "Painting" in str(json.loads(route.calls[0].request.content)["messages"])
    assert not settings.data_dir.exists()
    body = {**response.json()["draft"], "reviewed_at": "2026-10-13"}
    assert client.post("/api/specs/09 91 00", json=body, headers={"X-Admin-Token": "reviewer-test-token"}).status_code == 404


@pytest.mark.parametrize("section,title", [("../bad", "Title"), ("9 91 00", "Title"), ("09 91 00", ""),
                                           ("09 91 00", "  "), ("09 91 00", "x" * 161)])
def test_new_section_validation(client, monkeypatch, section, title):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    assert client.post("/api/specs/draft", params={"section": section, "title": title}, content=pdf()).status_code == 422
