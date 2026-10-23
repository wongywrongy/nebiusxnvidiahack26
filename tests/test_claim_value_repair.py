import asyncio
import json

import httpx
import pytest
import respx
from pydantic import SecretStr

from api.config import FORCE_MOCK, settings
from api.pipeline import extract, metrics, spec_check, verify
from api.providers.budget import BudgetExceeded
from api.schemas import Claim, ClaimsOut, Requirement, Usage


QUOTE = "L70 > 64,000 hours"


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    token = FORCE_MOCK.set(False)
    yield
    FORCE_MOCK.reset(token)


def original(**changes):
    claim = Claim(id="life", product="Alpha-1", manufacturer="Synthetic maker", property="l70_hours",
                  value=64000, unit="hr", page=1, quote=QUOTE, scope="product_wide", scope_quote=QUOTE)
    return ClaimsOut(product="Alpha-1", manufacturer="Synthetic maker", model="Alpha-1", claims=[
        claim.model_copy(update=changes),
        Claim(id="warranty", product="Alpha-1", manufacturer="Synthetic maker", property="warranty_years",
              value=7, unit="yr", page=1, quote="Warranty 7 years", scope="product_wide", scope_quote="Warranty 7 years")])


def correction(**changes):
    return {"id":"life", "property":"l70_hours", "value":">64000", "quote":QUOTE, **changes}


def run(monkeypatch, first, repairs, *, page_text=None):
    calls = []
    async def call(task, schema, messages, ctx):
        calls.append(messages[0]["content"])
        usage = Usage(task=task, tier="extract", model="synthetic")
        if schema is extract.ClaimValueRepairs:
            payload = json.loads(messages[0]["content"].split("\n\n")[-1])
            assert {row["id"] for row in payload} == {"life"}
            assert not any("requirement" in row or "expected" in row for row in payload)
            return schema.model_validate({"claims":repairs}), usage
        return first.model_copy(deep=True), usage
    monkeypatch.setattr(extract.router, "call", call)
    pages = [{"page":1, "text":page_text or "Alpha-1. " + QUOTE + ". L80 > 64,000 hours. Warranty 7 years"}]
    counts = dict.fromkeys(metrics.FIELDS, 0)
    token = metrics.COUNTS.set(counts)
    try:
        result, usage = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages),
                                                          ["l70_hours", "warranty_years"]))
    finally:
        metrics.COUNTS.reset(token)
    return result, usage, calls, counts


def test_one_bounded_value_repair_preserves_valid_claims_and_counts_every_read(live, monkeypatch):
    result, usage, calls, counts = run(monkeypatch, original(), [correction()])
    assert len(calls) == len(usage) == 2
    assert {c.property:c.value for c in result.claims} == {"l70_hours":">64000", "warranty_years":7}
    assert counts["claims_extracted"] == 3 and counts["claims_kept"] == 2
    assert not extract.value_quoted(64000, QUOTE, "l70_hours")
    assert result.model == "Alpha-1" and result.selection is None


def test_repair_keeps_original_quote_when_whitespace_differs(live, monkeypatch):
    result, _, _, _ = run(monkeypatch, original(), [correction(quote="L70\n> 64,000 hours")])
    life = next(c for c in result.claims if c.property == "l70_hours")
    assert life.value == ">64000" and life.quote == QUOTE


def test_correction_cannot_borrow_a_different_number_from_the_same_quote(live, monkeypatch):
    quote = QUOTE + " at 25 C"
    assert extract.value_quoted(25, quote, "l70_hours")  # Presence alone cannot bind a number to its metric.
    result, _, calls, _ = run(monkeypatch, original(quote=quote, scope_quote=quote),
        [correction(value=25, quote=quote)], page_text="Alpha-1. " + quote + ". Warranty 7 years")
    assert len(calls) == 2 and [c.property for c in result.claims] == ["warranty_years"]


@pytest.mark.parametrize("repairs", [
    [correction(id="another")], [correction(property="watts")], [correction(quote="L70 > 65,000 hours")],
    [correction(value=64000)], [correction(), correction(value=">99999")], []])
def test_unresolved_unknown_or_duplicate_corrections_cannot_rescue_a_claim(live, monkeypatch, repairs):
    result, _, calls, _ = run(monkeypatch, original(), repairs)
    assert len(calls) == 2  # Never recursively correct the correction.
    assert [c.property for c in result.claims] == ["warranty_years"]


@pytest.mark.parametrize("changes", [{"page":99}, {"quote":"not on this page"}, {"unit":"yr"},
                                      {"value":None}, {"property":"l80_hours"}, {"quote":"L80 > 64,000 hours"}])
def test_unquoted_wrong_metric_unit_or_unstated_values_do_not_trigger_repair(live, monkeypatch, changes):
    _, _, calls, _ = run(monkeypatch, original(**changes), [])
    assert len(calls) == 1


def test_value_repair_cannot_promote_an_unselected_option(live, monkeypatch):
    first = original(variant="L70", scope="option")
    forged = correction(model="Beta-2", variant=None, scope="product_wide", selection_quote="Selected: Alpha-1")
    result, _, _, _ = run(monkeypatch, first, [forged])
    life = next(c for c in result.claims if c.property == "l70_hours")
    assert life.variant == "L70" and life.scope == "option" and life.selection_quote is None
    assert "l70_hours" not in verify._unambiguous(result.claims)
    req = Requirement(id="limit", section="test", paragraph="", property="l70_hours", operator="gte", value=60000, text="Synthetic limit")
    assert spec_check.check([req], result.claims, {"product_data"})[0].verdict == "unverified"


def test_mock_extraction_never_invokes_live_correction(monkeypatch):
    monkeypatch.setattr(settings, "speccheck_mode", "mock")
    result, usage, calls, _ = run(monkeypatch, original(), [correction()])
    assert len(calls) == len(usage) == 1
    assert [c.property for c in result.claims] == ["warranty_years"]


def test_correction_cap_failure_propagates_for_typed_run_invalidity(live, monkeypatch):
    async def call(task, schema, messages, ctx):
        if schema is extract.ClaimValueRepairs:
            raise BudgetExceeded("Synthetic correction cap")
        return original(), Usage(task=task, tier="extract", model="synthetic")
    monkeypatch.setattr(extract.router, "call", call)
    pages = [{"page":1,"text":"Alpha-1. " + QUOTE}]
    with pytest.raises(BudgetExceeded, match="correction cap"):
        asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["l70_hours"]))


def test_schema_and_bounded_correction_use_the_real_provider_wire(live, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "nebius_api_key", SecretStr("synthetic-bound-repair-key"))
    def reply(payload):
        return httpx.Response(200,json={"choices":[{"message":{"content":json.dumps(payload)},"finish_reason":"stop"}],
                                       "usage":{"prompt_tokens":100,"completion_tokens":20}})
    with respx.mock as http:
        route = http.post(settings.nebius_base_url.rstrip('/')+'/chat/completions').mock(side_effect=[
            reply(original().model_dump()),reply({"claims":[correction()]})])
        pages = [{"page":1,"text":"Alpha-1. " + QUOTE + ". Warranty 7 years"}]
        result,_ = asyncio.run(extract.extract_claims(None,pages,extract.all_product_data(pages),["l70_hours","warranty_years"]))
        assert len(route.calls) == 2
        bodies = [json.loads(call.request.content) for call in route.calls]
        assert all(body["model"] == settings.model_extract and "tools" not in body for body in bodies)
        schema = bodies[0]["response_format"]["json_schema"]["schema"]
        assert "model" in schema["required"] and {"type":"null"} in schema["properties"]["model"]["anyOf"]
        assert next(c for c in result.claims if c.property == "l70_hours").value == ">64000"
