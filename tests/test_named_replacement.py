"""W3: a successor named in a discontinuation notice's text goes first; the current sheet reuses verify's own proof.

Synthetic sources only. Model calls go through respx; web and verify are stubbed as in test_replacement_proposals.
"""

import asyncio
import json

import pytest
import respx

from api.config import settings
from api.pipeline import fix
from api.providers import budget
from api.schemas import ClaimsOut, Compare, CompareRow, Evidence, Finding, ReplacementOut, Requirement
from api.web import WebClient

NOTICE = "https://maker.test/notice"
NAMED = "https://maker.test/zx-20.pdf"
OTHER = "https://other.test/troffer.pdf"
CURRENT = "https://maker.test/zx-12-current.pdf"
TEXT = ("Discontinuation notice. As of June 30, 2024, the ZX-12 family will be discontinued. "
        "Please convert this business to the ZX-20 family, its direct replacement.")
SHEET = "Model ZX-20. Warranty 6 years."
OCR = "Old family New\nZX-12 A12 ( flat frame) ZX-20 A12\nZX-12 SWL ( flat frame) ZX-20 SWL"
REQ = Requirement(id="w", section="test", paragraph="", property="warranty_years", operator="gte", value=5, unit="yr",
                  text="Five year warranty")
RETIRED = Finding(id="status-discontinued", check="status", verdict="fail", severity="major", title="Discontinued",
                  quote="the ZX-12 family will be discontinued", evidence=[Evidence(url=NOTICE, tier="manufacturer", title="Notice")])
CASE = {"id": "synthetic", "fixture": None, "title": "LED troffer, offices", "submittal": [{"role": "product_data"}],
        "manufacturer_domains": ["maker.test"]}
SUBMITTED = ClaimsOut(product="ZX-12", manufacturer="Maker", model="ZX-12", claims=[])


def claims(model):
    return ClaimsOut(product=model, manufacturer="Maker", model=model, claims=[dict(
        id="w", product=model, model=model, manufacturer="Maker", property="warranty_years", value=6, unit="yr",
        page=1, quote="Warranty 6 years", scope="product_wide", scope_quote="Warranty 6 years")])


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "evidence_dir", tmp_path / "evidence")
    queries = []

    async def search(self, query, *args, **kwargs):
        queries.append(query)
        return [{"url": NAMED, "title": "ZX-20"}] if "ZX-20" in query else [{"url": OTHER, "title": "Other troffer"}]

    async def extract(self, urls, *args, **kwargs):
        pages = {NOTICE: TEXT, NAMED: SHEET, OTHER: SHEET.replace("ZX-20", "QT-4"), CURRENT: SHEET.replace("ZX-20", "ZX-12")}
        return [{"url": u, "raw_content": pages[u]} for u in urls if u in pages]

    async def verified(*args, **kwargs):
        return [], [], [], 0, None
    async def images(self, url):
        return [OCR] if url == NOTICE else []
    monkeypatch.setattr(WebClient, "image_text", images)
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    monkeypatch.setattr(fix.verify, "verify", verified)
    return queries


def model_replies(replacement: ReplacementOut, ocr: ReplacementOut = ReplacementOut()):
    """The notice-text call gets `replacement`, the OCR call `ocr`; every data sheet read gets that sheet's model."""
    def reply(request):
        content = json.dumps(json.loads(request.content)["messages"])
        body = (ocr.model_dump_json() if "read by OCR" in content else replacement.model_dump_json() if "discontinuation notice" in content
                else claims(next(m for m in ("ZX-20", "QT-4", "ZX-12") if m in content)).model_dump_json())
        return respx.MockResponse(200, json={"choices": [{"message": {"content": body}}]})
    respx.post(settings.nebius_base_url + "chat/completions").mock(side_effect=reply)


@respx.mock
def test_a_quoted_successor_is_searched_and_ranked_first(live):
    model_replies(ReplacementOut(product="ZX-20", quote="Please convert this business to the ZX-20 family, its direct replacement."))
    result, usage, _ = asyncio.run(fix._fix(CASE, "currency", [RETIRED], [REQ], SUBMITTED, 2, 40))
    assert any("ZX-20" in q for q in live)
    assert result.candidates[0].source_url == NAMED
    assert {a.source_url: a.origin for a in result.alternates}[NAMED] == "named_replacement"
    assert any(u.task == "fix: replacement" for u in usage)
    assert result.named.source == "text" and result.named.url == NOTICE


@pytest.mark.parametrize("reply", [
    ReplacementOut(product="ZX-20", quote="The ZX-20 family replaces it."),  # sentence not on the notice
    ReplacementOut(product="ZX-30", quote="Please convert this business to the ZX-20 family, its direct replacement."),  # name not in it
    ReplacementOut(),
])
@respx.mock
def test_an_unquoted_successor_is_dropped(live, reply):
    model_replies(reply)
    result, _, _ = asyncio.run(fix._fix(CASE, "currency", [RETIRED], [REQ], SUBMITTED, 2, 40))
    assert not any("ZX-2" in q or "ZX-3" in q for q in live)
    assert [c.source_url for c in result.candidates] == [OTHER]
    assert all(a.origin == "search" for a in result.alternates)


@respx.mock
def test_a_cap_during_the_named_lookup_ends_cleanly(live, monkeypatch):
    model_replies(ReplacementOut())
    async def capped(*args, **kwargs):
        raise budget.BudgetExceeded("Tavily credit cap reached")
    monkeypatch.setattr(fix, "named_replacement", capped)
    warnings = []
    async def warn(stage, reason):
        warnings.append((stage, reason))
    result, _, _ = asyncio.run(fix._fix(CASE, "currency", [RETIRED], [REQ], SUBMITTED, 2, 40, on_warning=warn))
    assert [c.source_url for c in result.candidates] == [OTHER] and warnings and warnings[0][0] == "fix"


@respx.mock
def test_the_current_sheet_reuses_the_items_own_still_made_quote(live):
    model_replies(ReplacementOut())
    outdated = Finding(id="currency-outdated", check="currency", verdict="outdated", severity="major", title="Outdated",
                       compare=Compare(left_label="Submitted", right_label="Current", verdict="changed", rows=[CompareRow(
                           property="warranty_years", label="Warranty", submitted="5 yr", current="6 yr", changed=True,
                           source_url=CURRENT, quote="Warranty 6 years")]),
                       evidence=[Evidence(url=CURRENT, tier="manufacturer", title="ZX-12 current sheet")])
    active = Finding(id="status-active", check="status", verdict="pass", severity="info", title="Still made", quote="ZX-12 in production",
                     evidence=[Evidence(url=CURRENT, tier="manufacturer", title="ZX-12", excerpt="ZX-12 in production")])
    still = lambda result: next(k for k in result.candidates[0].checks if k.label == "Still made")
    result, _, _ = asyncio.run(fix._fix(CASE, "currency", [outdated], [REQ], SUBMITTED, 1, 40, item_findings=[outdated, active]))
    assert result.candidates[0].source_url == CURRENT and still(result).ok is True and still(result).evidence
    result, _, _ = asyncio.run(fix._fix(CASE, "currency", [outdated], [REQ], SUBMITTED, 1, 40, item_findings=[outdated]))
    assert still(result).ok is None  # no quoted proof from the item's own check: stays unconfirmed


@respx.mock
def test_a_successor_read_from_an_image_on_the_notice_is_labelled_and_first(live):
    model_replies(ReplacementOut(), ocr=ReplacementOut(product="ZX-20 A12", quote="ZX-12 A12 ( flat frame) ZX-20 A12"))
    result, _, _ = asyncio.run(fix._fix(CASE, "currency", [RETIRED], [REQ], SUBMITTED, 2, 40))
    assert result.named.source == "image_ocr" and result.named.name == "ZX-20 A12"
    assert result.candidates[0].source_url == NAMED and result.alternates[0].origin == "named_replacement"


@pytest.mark.parametrize("ocr", [
    ReplacementOut(product="ZX-20 A12", quote="ZX-12 A12 flat frame ZX-20 A12 replacement"),  # not a line of the OCR text
    ReplacementOut(product="ZX-30", quote="ZX-12 A12 ( flat frame) ZX-20 A12"),  # name not in the line
])
@respx.mock
def test_an_unquoted_ocr_successor_is_dropped(live, ocr):
    model_replies(ReplacementOut(), ocr=ocr)
    result, _, _ = asyncio.run(fix._fix(CASE, "currency", [RETIRED], [REQ], SUBMITTED, 2, 40))
    assert result.named is None and [c.source_url for c in result.candidates] == [OTHER]


@respx.mock
def test_page_images_are_ocrd_once_and_cached(monkeypatch, tmp_path):
    import base64
    from api import web
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    png = base64.b64encode(b"\x89PNG" + b"0" * 300).decode()
    page = respx.get(NOTICE).respond(200, text=f'<p>replacements:</p><img src="data:image/png;base64,{png}">')
    monkeypatch.setattr(web, "_ocr", lambda data: OCR if data.startswith(b"\x89PNG") else "")
    assert asyncio.run(WebClient(None).image_text(NOTICE)) == [OCR]
    assert asyncio.run(WebClient(None).image_text(NOTICE)) == [OCR] and page.call_count == 1
