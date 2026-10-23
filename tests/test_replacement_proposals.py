"""Synthetic sources only: proposing a SKU cannot select the original package or invent proof."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
import hashlib

import httpx
import pytest
import respx

from api import release
from api.config import settings
from api.pipeline import decide, extract, fix, verify
from api.schemas import ClaimsOut, Evidence, Finding, Fix, FixCandidate, ReportOut, Requirement, Selection, Usage, VerifyOut
from api.web import WebClient


SKU = "ZX-12-D1"
CATALOG = f"Model ZX-12. Catalog number: {SKU}. D1 dimming to 2%. D10 dimming to 10%. Warranty 6 years."


def payload(sku=SKU):
    return ClaimsOut(product="ZX-12", manufacturer="Synthetic maker", model="ZX-12",
        selection=Selection(model=sku, page=1, quote=f"Catalog number: {sku}"), claims=[
            dict(id="dim", product="ZX-12", model="ZX-12", manufacturer="Synthetic maker", property="dim_min_percent",
                 value=2, unit="%", page=1, quote="D1 dimming to 2%", variant="D1", scope="option",
                 scope_quote="D1 dimming to 2%"),
            dict(id="w", product="ZX-12", model="ZX-12", manufacturer="Synthetic maker", property="warranty_years",
                 value=6, unit="yr", page=1, quote="Warranty 6 years", scope="product_wide", scope_quote="Warranty 6 years")])


@pytest.mark.parametrize("propose,sku,source,confirmed", [
    (False, SKU, CATALOG, False), (True, SKU, CATALOG, True),
    (True, "ZX-12-D10", CATALOG.replace(SKU, "ZX-12-D10"), False),
    (True, SKU, CATALOG.replace(SKU, "ZX-12-D10"), False),
    (True, "ZX-12-XX", CATALOG.replace(SKU, "ZX-12-XX"), False),
    (True, SKU, "Ordering example: " + CATALOG, False),
])
@respx.mock
def test_proposal_protocol_and_original_selection_stay_separate(monkeypatch, tmp_path, propose, sku, source, confirmed):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    route = respx.post(settings.nebius_base_url + "chat/completions").respond(200, json={
        "choices": [{"message": {"content": payload(sku).model_dump_json()}}]})
    pages = [{"page": 1, "text": source}]
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages),
        ["dim_min_percent", "warranty_years"], propose=propose))
    assert ("dim_min_percent" in verify._unambiguous(out.claims)) is confirmed
    request = json.loads(route.calls[0].request.content)
    assert "tools" not in request
    assert "origin" not in request["response_format"]["json_schema"]["schema"]["$defs"]["Selection"]["properties"]
    if confirmed:
        assert out.selection.origin == "agent_proposal" and out.model == SKU
        assert not extract.selection_supported(out.selection, {1: source})
        release._claims(out, out.claims, out.selection, {1: source}, allow_proposal=True)
        with pytest.raises(ValueError, match="Selected configuration"):
            release._claims(out, out.claims, out.selection, {1: source})
    if propose:
        assert any("at most one complete manufacturer-printed" in m["content"] for m in request["messages"])


@pytest.mark.parametrize("part,base,expected", [("D1",False,True), ("D",False,False), ("D10",False,False),
    ("ZX-12",True,True), ("ZX-1",True,False), ("12",True,False), ("Other ZX-12",True,False)])
def test_proposal_options_match_complete_components_and_identity_prefix(part, base, expected):
    selection = Selection(model=SKU, page=1, quote=f"Catalog number: {SKU}", origin="agent_proposal")
    assert extract.selection_matches(selection, part, base=base) is expected


@pytest.mark.parametrize("origin,label", [("submitted", "Selected"), ("agent_proposal", "Catalog number")])
def test_configuration_quote_cannot_end_inside_a_longer_sku(origin, label):
    selection = Selection(model=SKU, page=1, quote=f"{label}: {SKU}", origin=origin)
    assert not extract.selection_supported(selection, {1: f"{label}: {SKU}0. Other SKU: {SKU}."}, allow_proposal=True)


def test_forged_proposal_cannot_enter_original_extraction(monkeypatch):
    async def read(*args):
        out = payload()
        out.selection.origin = "agent_proposal"
        return out, Usage(task="extract_claims", tier="extract", model="synthetic")
    monkeypatch.setattr(extract, "_read_claims", read)
    pages = [{"page": 1, "text": CATALOG}]
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["dim_min_percent"]))
    assert out.selection is None and not verify._unambiguous(out.claims)


@pytest.mark.parametrize("web_model,accepted", [(SKU, True), ("ZX-12-D10", False)])
def test_web_values_stay_bound_to_proposed_sku_and_conditional_listings_stay_unknown(web_model, accepted):
    submitted = payload()
    submitted.selection.origin = "agent_proposal"
    submitted.model = SKU
    url = "https://maker.test/current"
    out = VerifyOut(status="unknown", current_values=[
        dict(property="dim_min_percent", value=2, unit="%", quote="D1 dimming to 2%", variant="D1",
             model=web_model, identity_quote=f"Model {web_model}", source_url=url, scope="option", scope_quote="D1 dimming to 2%"),
        dict(property="dlc_listed", value="DLC Premium", quote="DLC Premium for certain configurations only",
             model=web_model, identity_quote=f"Model {web_model}", source_url=url, scope="product_wide",
             scope_quote="DLC Premium for certain configurations only")])
    text = f"Model {SKU}. Model {web_model}. D1 dimming to 2%. DLC Premium for certain configurations only."
    verify.gate(out, [{"url":url,"raw_content":text}], submitted=submitted)
    values = verify._unambiguous(out.current_values)
    assert ("dim_min_percent" in values) is accepted
    assert "dlc_listed" not in values


@pytest.mark.parametrize("active", [False, True])
@respx.mock
def test_fix_proposes_with_quotes_but_still_requires_availability(monkeypatch, tmp_path, active):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "evidence_dir", tmp_path / "evidence")
    url = "https://maker.test/catalog.pdf"
    async def search(*args, **kwargs):
        return [{"url": url, "title": "Synthetic catalog"}]
    async def fetch(*args, **kwargs):
        return [{"url": url, "raw_content": CATALOG}]
    async def verified(*args, **kwargs):
        rows = [Finding(id="currency-current",check="currency",verdict="pass",severity="info",title="Current",
            evidence=[Evidence(url=url,tier="manufacturer",title="Synthetic current sheet",excerpt="Warranty 6 years")])]
        if active:
            rows.append(Finding(id="status-active",check="status",verdict="pass",severity="info",title="Available",
                evidence=[Evidence(url=url,tier="manufacturer",title="Synthetic availability double",excerpt=SKU)]))
        return rows, [], [], 0, None
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", fetch)
    monkeypatch.setattr(fix.verify, "verify", verified)
    respx.post(settings.nebius_base_url + "chat/completions").respond(200, json={
        "choices": [{"message": {"content": payload().model_dump_json()}}]})
    req = Requirement(id="dim", section="test", paragraph="", property="dim_min_percent", operator="lte", value=4, unit="%", text="Dimming")
    old = Finding(id="old",check="status",verdict="fail",severity="major",title="Retired")
    result, _, _ = asyncio.run(fix._fix({"id":"synthetic", "fixture":None,"title":"Luminaire", "submittal":[{"role":"product_data"}]},
        "currency", [old], [req], ClaimsOut(product="Previous",manufacturer="Synthetic maker",claims=[]), 1, 40))
    candidate, = result.candidates
    assert candidate.passes is active and candidate.selection.origin == "agent_proposal"
    assert ("SpecCheck proposal: " + SKU in result.suggest) is active
    assert all(check.evidence for check in candidate.checks if check.ok is True)


def test_proposal_archive_is_rechecked_and_report_preserves_authorship(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "evidence_dir", tmp_path)
    body = CATALOG.encode()
    path = tmp_path / "catalog.txt"; path.write_bytes(body)
    now = datetime.now(timezone.utc)
    source = Evidence(url="https://maker.test/catalog", tier="manufacturer", title="Synthetic catalog", archived_path=path.name,
        sha256=hashlib.sha256(body).hexdigest(),retrieved_at=now.isoformat())
    selected = payload().selection.model_copy(update={"origin":"agent_proposal"})
    candidate = FixCandidate(name="Synthetic catalog",source_url=source.url,documents=[source],passes=True,selection=selected,checks=[])
    assert release._selection_proof(candidate, selected, now - timedelta(hours=1), now + timedelta(minutes=1))
    selected.quote = "Catalog number: ZX-12-D10"
    assert not release._selection_proof(candidate, selected, now - timedelta(hours=1), now + timedelta(minutes=1))
    suggestion = f"SpecCheck proposal: {SKU}. Confirm configuration before ordering."
    finding = Finding(id="old",check="status",verdict="fail",severity="major",title="Retired",
        fix=Fix(head="Checked proposal",query="",suggest=suggestion,candidates=[candidate]))
    async def report(*args, **kwargs):
        return ReportOut(summary="",note_to_subcontractor="",finding_titles={},why_it_matters={}), Usage(task="report",tier="write",model="synthetic")
    monkeypatch.setattr(decide.router, "call", report)
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    out, _ = asyncio.run(decide.report(None, "Synthetic package", "send_back", [finding]))
    assert suggestion in out.note_to_subcontractor
