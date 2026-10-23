import asyncio
import json

import httpx
import pytest
import respx

from api.config import settings
from api.pipeline import verify
from api.pipeline.investigate import investigate
from api.schemas import Claim, ClaimsOut, Investigation, VerifyOut
from api.web import WebClient

URL = "https://maker.test/x.pdf"
SUBMITTED = ClaimsOut(product="X", model="X", manufacturer="Maker", document_revision="Rev A", claims=[
    Claim(id="w", product="X", model="X", manufacturer="Maker", property="watts", value=10, unit="W",
          page=1, quote="Power 10 W", scope="product_wide", scope_quote="Power 10 W")])


@pytest.mark.parametrize("status,required,availability,expected", [
    ("unknown", [], False, False), ("unknown", [], True, True),
    ("active", [], True, False), ("unknown", ["macadam_steps"], False, True),
])
def test_replacement_research_checks_required_gaps_even_with_a_revision(monkeypatch, status, required, availability, expected):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    observed = []
    async def search(*args, **kwargs):
        return [{"url":URL}]
    async def extract(*args, **kwargs):
        return [{"url":URL, "raw_content":"Model X. Rev A. Power 10 W. X is currently available."}]
    async def read(*args, **kwargs):
        return VerifyOut(status=status, status_quote="X is currently available.", current_revision="Rev A", current_values=[
            dict(property="watts",value=10,unit="W",quote="Power 10 W",scope="product_wide",scope_quote="Power 10 W",
                 model="X",identity_quote="Model X",source_url=URL)]), []
    async def research(case, *args):
        observed.append(case)
        return Investigation()
    monkeypatch.setattr(WebClient,"search",search)
    monkeypatch.setattr(WebClient,"extract",extract)
    monkeypatch.setattr(verify,"read_sources",read)
    monkeypatch.setattr(verify,"investigate",research)
    _,_,_,_,inv = asyncio.run(verify.verify({"id":"synthetic", "manufacturer_domains":["maker.test"],
        "required_properties":required,"require_availability":availability},SUBMITTED))
    assert bool(observed) is expected and (inv is not None) is expected
    if expected:
        assert observed[0]["unconfirmed_properties"] == required
        assert observed[0]["require_availability"] is availability


def test_final_read_prioritizes_new_document_status_and_supplementary_evidence(monkeypatch):
    monkeypatch.setattr(settings,"speccheck_mode","live")
    status = {"url":"https://maker.test/status", "raw_content":"Model X. X is currently available."}
    supplement = {"url":"https://maker.test/support", "raw_content":"Model X. 2 MacAdam steps."}
    document = {"url":URL, "raw_content":"Model X. Rev A. Power 10 W."}
    observed = []
    async def search(*args, **kwargs):
        return [{"url":"https://maker.test/old"}]
    async def extract(*args, **kwargs):
        return [{"url":"https://maker.test/old", "raw_content":"Model X. Rev A."}]
    async def read(fx, submitted, pages, investigated=False, **kwargs):
        observed.append([p["url"] for p in pages])
        return VerifyOut(status="active" if investigated else "unknown", current_revision="Rev A",
                         status_quote="X is currently available." if investigated else None), []
    async def research(*args):
        inv = Investigation(outcome="found")
        inv._document_url = URL
        inv._pages = [supplement,status,document,document]
        inv._verified = VerifyOut(status="active",status_quote="X is currently available.")
        return inv
    monkeypatch.setattr(WebClient,"search",search)
    monkeypatch.setattr(WebClient,"extract",extract)
    monkeypatch.setattr(verify,"read_sources",read)
    monkeypatch.setattr(verify,"investigate",research)
    findings,_,_,_,inv = asyncio.run(verify.verify({"id":"synthetic","manufacturer_domains":["maker.test"],
                                                  "require_availability":True},SUBMITTED))
    assert inv.outcome == "found"
    assert observed[-1] == [URL,status["url"],supplement["url"]]
    assert any(f.id == "status-active" and f.evidence[0].url == status["url"] for f in findings)
    assert SUBMITTED.selection is None


@respx.mock
def test_native_tool_request_carries_gaps_and_forbids_inferred_availability(monkeypatch,tmp_path):
    monkeypatch.setattr(settings,"speccheck_mode","live")
    monkeypatch.setattr(settings,"cache_dir",tmp_path)
    route = respx.post(settings.nebius_base_url+"chat/completions").mock(return_value=httpx.Response(200,json={
        "choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"No quoted source"}}],
        "usage":{"prompt_tokens":100,"completion_tokens":20}}))
    asyncio.run(investigate({"id":"synthetic","candidate_url":URL,"require_availability":True,
                            "unconfirmed_properties":["macadam_steps"]},SUBMITTED,WebClient(None)))
    body = json.loads(route.calls[0].request.content)
    user = json.loads(body["messages"][1]["content"])
    assert user["require_availability"] is True and user["unconfirmed_properties"] == ["macadam_steps"]
    assert user["candidate_url"] == URL and user["submitted_label"] is None
    assert "absence of a discontinuation notice is not availability evidence" in body["messages"][0]["content"]
    assert "response_format" not in body and body["tools"]
