import asyncio
import json

import pytest

from api.config import settings
from api.pipeline import extract, spec_check, verify
from api.schemas import ClaimsOut, TriageOut, Usage, VerifyOut


def test_complete_chunks_reach_tail_and_preserve_each_call(monkeypatch):
    monkeypatch.setattr(settings, "max_page_chars", 1000)
    text = "Introductory material.\n" * 800 + "Warranty 7 years."
    pages = [{"page": 4, "text": text}]
    chunks = list(extract.page_batches(pages, 1000))
    assert len(chunks) > 1
    assert all(sum(len(p["text"]) for p in batch) <= 12000 for batch in chunks)
    seen = []
    async def call(task, schema, messages, ctx):
        batch = json.loads(messages[0]["content"].split("\n\n")[-1])
        seen.extend(batch)
        claims = []
        if any("Warranty 7 years." in p["text"] for p in batch):
            claims = [{"id": "w", "product": "X", "manufacturer": "Maker", "property": "warranty_years",
                       "value": 7, "unit": "yr", "page": 4, "quote": "Warranty 7 years."}]
        return ClaimsOut(product="X", manufacturer="Maker", claims=claims), Usage(task=task, tier="extract", model="test")
    monkeypatch.setattr(extract.router, "call", call)
    # Even a missing triage label must not silently hide a readable page.
    claims, usage = asyncio.run(extract.extract_claims(None, pages, TriageOut(pages=[]), ["warranty_years"]))
    assert len(usage) == len(chunks) and len(claims.claims) == 1
    assert claims.claims[0].page == 4
    assert "Warranty 7 years." in seen[-1]["text"]


def test_property_allowlist_reaches_schema_and_drops_unrequested_aliases(monkeypatch):
    async def call(task, schema, messages, ctx):
        assert schema.model_json_schema()["$defs"]["Claim"]["properties"]["property"]["enum"] == ["watts"]
        claims = [{"id": prop, "product": "X", "manufacturer": "M", "property": prop,
                   "value": 10, "unit": "W", "page": 1, "quote": "Power draw 10 W"}
                  for prop in ("watts", "power_draw_w")]
        return ClaimsOut(product="X", manufacturer="M", claims=claims), Usage(task=task, tier="extract", model="test")
    monkeypatch.setattr(extract.router, "call", call)
    pages = [{"page": 1, "text": "Power draw 10 W"}]
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["watts"]))
    assert [c.property for c in out.claims] == ["watts"]


@pytest.mark.parametrize("other", ["Alpha-1", "Beta-2", None])
def test_chunks_cannot_pool_properties_from_other_or_unidentified_products(monkeypatch, other):
    pages = [{"page": 1, "text": "Model Alpha-1. VOC 10 g/L"},
             {"page": 2, "text": (f"Model {other}. " if other else "") + "Service temperature 180 F"}]
    monkeypatch.setattr(extract, "page_batches", lambda pages, limit: ([p] for p in pages))
    async def read(fx, batch, properties):
        first = batch[0]["page"] == 1
        model = "Alpha-1" if first else other or "Unidentified product"
        quote = "VOC 10 g/L" if first else "Service temperature 180 F"
        return ClaimsOut(product=model, manufacturer="Maker", model=model if first or other else None,
            claims=[{"id": model, "product": model, "manufacturer": "Maker", "property": "voc" if first else "temperature",
                     "value": 10 if first else 180, "page": batch[0]["page"], "quote": quote,
                     "scope": "product_wide", "scope_quote": quote}]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract, "_read_claims", read)
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["voc", "temperature"]))
    reqs = [dict(id="voc", property="voc", operator="lte", value=250),
            dict(id="temp", property="temperature", operator="gte", value=120)]
    from api.schemas import Requirement
    findings = spec_check.check([Requirement(**r, section="test", paragraph="", text="Limit") for r in reqs], out.claims, {"product_data"})
    assert [f.verdict for f in findings] == (["pass", "pass"] if other == "Alpha-1" else ["unverified", "unverified"])
    assert len(out.claims) == 2  # Both quotes remain visible even when attribution is unconfirmed.


@pytest.mark.parametrize("claim_model", ["Beta-2", None])
def test_selected_driver_cannot_reactivate_a_different_products_claim(monkeypatch, claim_model):
    from api.schemas import Selection
    pages = [{"page": 1, "text": "Selected: Alpha-1 EZ1. EZ1 power 10 W. Beta-2 power 20 W"}]
    async def read(*args):
        return ClaimsOut(product="Beta-2", manufacturer="Maker", model="Alpha-1",
            selection=Selection(model="Alpha-1 EZ1", page=1, quote="Selected: Alpha-1 EZ1"),
            claims=[{"id": "other", "product": "Beta-2", "model": claim_model, "manufacturer": "Maker",
                     "property": "watts", "value": 20, "unit": "W", "page": 1, "quote": "Beta-2 power 20 W",
                     "scope": "product_wide", "scope_quote": "Beta-2 power 20 W"}]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract, "_read_claims", read)
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["watts"]))
    assert out.selection is None and not verify._unambiguous(out.claims)


def test_other_selected_product_cannot_bind_a_shared_driver(monkeypatch):
    from api.schemas import Selection
    pages = [{"page": 1, "text": "Model Alpha-1. Selected: Beta-2 EZ1. EZ1 power 10 W"}]
    async def read(*args):
        return ClaimsOut(product="Alpha-1", manufacturer="Maker", model="Alpha-1",
            selection=Selection(model="Beta-2 EZ1", page=1, quote="Selected: Beta-2 EZ1"),
            claims=[{"id": "power", "product": "Alpha-1", "manufacturer": "Maker", "property": "watts",
                     "value": 10, "unit": "W", "page": 1, "quote": "EZ1 power 10 W", "variant": "EZ1"}]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract, "_read_claims", read)
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["watts"]))
    assert out.model == "Alpha-1" and out.selection is None and not verify._unambiguous(out.claims)
    assert out.claims[0].scope == "unknown"


@pytest.mark.parametrize("page", [None, 1, 99])
def test_quote_on_another_page_cannot_rescue_a_claim(monkeypatch, page):
    async def call(*args):
        return ClaimsOut(product="X", manufacturer="M", claims=[{
            "id": "c", "product": "X", "manufacturer": "M", "property": "measurement", "value": 10,
            "page": page, "quote": "Measurement 10"}]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract.router, "call", call)
    pages = [{"page": 1, "text": "Unrelated text"}, {"page": 2, "text": "Measurement 10"}]
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["measurement"]))
    assert not out.claims


@pytest.mark.parametrize("value,op,target,expected", [
    ("<50000", "gte", 50000, False), ("<50000", "gte", 40000, None),
    (">=50000", "gte", 50000, True), ("<2", "lte", 250, True),
    (">250", "lte", 250, False), ("<2", "eq", 2, False), ("<2", "eq", 1, None),
    ("~5", "gte", 5, None), ("Class 0", "eq", 0, True),
])
def test_numeric_bounds_are_not_exact_values(value, op, target, expected):
    assert spec_check.numeric_compare(value, None, target, None, op) is expected


def test_incompatible_units_remain_unknown():
    assert spec_check.numeric_compare(5, "W", 5, "hr", "eq") is None
    assert spec_check.numeric_compare(120, "min", 2, "hr", "eq") is True
    assert verify._same(2, 120, "hr", "min")
    assert not verify._same(2, 2, "hr", "min")
    assert not verify._same("≥50", 50) and not verify._same("~5", 5)


@pytest.mark.parametrize("value,quote,kept", [(50000, "At least 50,000 hours", False),
    (">=50000", "At least 50,000 hours", True), (2, "Less than 2 g/L", False), ("<2", "Less than 2 g/L", True)])
def test_prose_bounds_must_survive_extraction(value, quote, kept):
    assert extract.value_quoted(value, quote) is kept


def test_inclusive_prose_bound_is_preserved():
    assert extract.value_quoted(">=5", "Greater than or equal to 5 hours")
    assert not extract.value_quoted(5, "Greater than or equal to 5 hours")


def test_metric_and_unit_identity_are_independent_gates():
    assert not extract.metric_quoted("lumens", "Power draw 40 W")
    assert not extract.metric_quoted("watts", "Efficiency 40 lm/W")
    assert not extract.metric_quoted("watts", "Efficiency 40 lm / W")
    assert not extract.unit_quoted("hr", "Warranty 5 years")
    assert not extract.revision_supported("90G9", "UL category 90G9")
    assert extract.revision_supported("Rev B", "Document Rev B")
    assert extract.value_quoted(120, "not to exceed 120°F", "service_temp_max_f")


def test_web_reader_reads_after_the_first_bounded_batch(monkeypatch):
    text = "Earlier content.\n" * 1000 + "Warranty 7 years."
    calls = []
    async def call(task, schema, messages, ctx):
        sources = json.loads(messages[0]["content"].split("SOURCES:\n")[-1])
        calls.append(sources)
        values = [{"property": "warranty_years", "value": 7, "quote": "Warranty 7 years."}] if any(
            "Warranty 7 years." in p["text"] for p in sources) else []
        return VerifyOut(status="unknown", current_values=values), Usage(task=task, tier="verify", model="test")
    monkeypatch.setattr(verify.router, "call", call)
    pages = [{"url": "https://maker.test/sheet", "raw_content": text}]
    out, usage = asyncio.run(verify.read_sources(None, ClaimsOut(product="X", manufacturer="M", claims=[]), pages))
    verify.gate(out, pages)
    assert len(usage) == len(calls) > 1 and len(out.current_values) == 1


def test_postfix_minimum_preserves_bound_and_malformed_numbers_stay_unknown():
    from api.pipeline.extract import value_quoted
    from api.pipeline.spec_check import to_number
    assert value_quoted(">=80", "80 CRI minimum")
    assert not value_quoted(80, "80 CRI minimum")
    assert value_quoted("<=5", "5 g/L maximum")
    assert to_number("3/0") is None and to_number("1-1/0") is None
    assert to_number(float("nan")) is None
