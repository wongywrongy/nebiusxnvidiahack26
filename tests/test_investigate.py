"""Investigator protocol, evidence, caps and UI events; all provider HTTP is intercepted by respx."""

import asyncio
import json

import httpx
import pytest
import respx
from pydantic import SecretStr

from api.config import FORCE_MOCK, settings
from api.pipeline import fix, verify
from api.pipeline.cases import all_cases, get_case
from api.pipeline.investigate import TOOLS, investigate, tool_content
from api.pipeline.runner import Run, execute
from api.providers import budget, tavily, tokenfactory
from api.schemas import Claim, ClaimsOut, Finding, Investigation, Requirement, VerifyOut
from api.web import WebClient

CHAT = settings.nebius_base_url + "chat/completions"
URL = "https://maker.test/product.pdf"
CLAIMS = ClaimsOut(product="Product X", manufacturer="Maker", model="X", document_revision="Rev A", claims=[])
CASE = {"id": "test", "manufacturer_domains": ["maker.test"]}
FINAL = {"found": True, "document_url": URL, "revision_quote": "Rev B", "status": "active",
         "status_quote": "Product X is still made.", "note": "Exact model and revision found."}


def reply(tool=None, args=None, *, text=None, calls=None):
    message = {"role": "assistant", "content": text}
    if tool:
        message["tool_calls"] = calls or [{"id": "call-1", "type": "function", "function": {
            "name": tool, "arguments": json.dumps(args)}}]
    return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls" if tool else "stop", "message": message}],
                                   "usage": {"prompt_tokens": 100, "completion_tokens": 20}})


@pytest.fixture
def http(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "nebius_api_key", SecretStr("sk-investigator-test-0123456789"))
    monkeypatch.setattr(settings, "tavily_api_key", SecretStr("tvly-investigator-test-0123456789"))
    led = budget.LEDGER.set(budget.Ledger())
    item = budget.ITEM.set("test")
    mock = FORCE_MOCK.set(False)
    with respx.mock(assert_all_called=False) as http:
        http.post(tavily.API + "/map").respond(200, json={"results": []})
        yield http
    FORCE_MOCK.reset(mock)
    budget.ITEM.reset(item)
    budget.LEDGER.reset(led)


def sources(http, text="Product X. Rev B. Product X is still made."):
    http.post(tavily.API + "/search").respond(200, json={"results": [{"url": URL, "title": "Product X sheet"}]})
    http.post(tavily.API + "/extract").respond(200, json={"results": [{"url": URL, "raw_content": text}]})


def happy(http, final=None):
    sources(http)
    return http.post(CHAT).mock(side_effect=[reply("search", {"query": "Maker X data sheet", "topic": "news"}),
                                           reply("extract", {"url": URL}), reply("finish", final or FINAL)])


def test_search_extract_finish_is_verified_and_uses_native_tools(http):
    route = happy(http)
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "found" and inv._verified.current_revision == "Rev B" and inv._verified.status == "active"
    assert [s.tool for s in inv.steps] == ["search", "extract", "finish"]
    assert sum(s.credits for s in inv.steps) == 2
    assert len(inv._usage) == 3 and all(u.task == "investigate" for u in inv._usage)
    bodies = [json.loads(c.request.content) for c in route.calls]
    assert all(b["tools"] and b["tool_choice"] == "auto" and "response_format" not in b for b in bodies)
    assert all(b["reasoning_effort"] == "none" and b["chat_template_kwargs"] == {"enable_thinking": False} for b in bodies)
    assert bodies[1]["messages"][-1]["role"] == "tool" and bodies[1]["messages"][-1]["tool_call_id"] == "call-1"


@pytest.mark.parametrize("final", [{**FINAL, "revision_quote": "Rev C", "status_quote": "Discontinued", "status": "discontinued"},
                                  {**FINAL, "document_url": "https://maker.test/not-extracted.pdf"}])
def test_finish_cannot_launder_unfetched_quotes(http, final):
    happy(http, final)
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "not_found" and inv._verified.current_revision is None and inv._verified.status == "unknown"


def test_six_call_cap_including_parallel_tool_calls(http):
    sources(http)
    calls = [{"id": f"c-{i}", "function": {"name": "search", "arguments": json.dumps({"query": f"query {i}"})}}
             for i in range(9)]
    route = http.post(CHAT).mock(return_value=reply("search", calls=calls))
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "capped" and len(inv.steps) == 6 and len(route.calls) == 1


def test_eight_credit_cap_stops_before_the_next_web_call(http):
    route = http.post(tavily.API + "/map").respond(200, json={"results": [f"https://maker.test/{n}" for n in range(20)]})
    http.post(CHAT).mock(side_effect=[reply("map", {"url": f"https://maker.test/{n}", "instructions": "data sheet"})
                                      for n in range(3)])
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "capped" and len(route.calls) == 2
    assert sum(s.credits for s in inv.steps) == 8 and inv.steps[-1].credits == 0


def test_credit_cap_is_shared_by_investigations_for_the_same_item(http):
    route = http.post(tavily.API + "/map").respond(200, json={"results": [f"https://maker.test/{n}" for n in range(20)]})
    http.post(CHAT).mock(side_effect=[reply("map", {"url": "https://maker.test/1", "instructions": "sheet"}), reply(),
                                      reply("map", {"url": "https://maker.test/2", "instructions": "sheet"}),
                                      reply("map", {"url": "https://maker.test/3", "instructions": "sheet"})])
    asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    inv = asyncio.run(investigate(CASE, CLAIMS.model_copy(update={"product": "second"}), WebClient("test")))
    assert inv.outcome == "capped" and len(route.calls) == 2


def test_results_are_truncated_for_model_but_quotes_use_whole_pages(http):
    sources(http, "x" * 12000 + " Rev B. Product X is still made.")
    route = http.post(CHAT).mock(side_effect=[reply("extract", {"url": URL}), reply("finish", FINAL)])
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "found"
    body = json.loads(route.calls[-1].request.content)
    assert len(body["messages"][-1]["content"]) <= 6000 and len(inv._pages[0]["raw_content"]) > 12000


def test_extract_tool_excerpt_keeps_document_body_tail_and_valid_json(http):
    text = "navigation " * 1500 + "\n# Product X\nStatus: Discontinued.\n" + "body\t\n" * 3000 + "Revision C"
    encoded = tool_content("extract", [{"url": URL, "raw_content": text}])
    assert len(encoded) <= 6000
    page = json.loads(encoded)
    assert page["url"] == URL and "Status: Discontinued." in page["text"] and "Revision C" in page["text"]
    secret = settings.secret("nebius_api_key")
    assert secret not in tool_content("extract", [{"url": URL, "raw_content": "# Product X\n" + secret}])


@pytest.mark.parametrize("candidate,label", [(False, "Inbox family label"), (True, None)])
def test_investigator_gets_input_label_only_for_submitted_product(http, candidate, label):
    route = http.post(CHAT).mock(return_value=reply(text="No source found"))
    case = {**CASE, "product": "Inbox family label", **({"candidate_url": URL} if candidate else {})}
    asyncio.run(investigate(case, CLAIMS, WebClient("test")))
    user = json.loads(json.loads(route.calls[0].request.content)["messages"][1]["content"])
    assert user["submitted_label"] == label


def test_source_schema_limits_properties_without_limiting_alternatives(http):
    route = http.post(CHAT).mock(return_value=reply(text='{"status":"unknown"}'))
    claim = Claim(id="measurement", product="X", manufacturer="Maker", property="measurement", value=10)
    asyncio.run(verify.read_sources("test", CLAIMS.model_copy(update={"claims": [claim]}), [], submitted_label="Inbox family label"))
    assert "Inbox family label" in json.loads(route.calls[-1].request.content)["messages"][-1]["content"]
    schema = json.loads(route.calls[-1].request.content)["response_format"]["json_schema"]["schema"]
    assert schema["$defs"]["PropertyValue"]["properties"]["property"]["enum"] == ["measurement"]
    assert "maxItems" not in schema["properties"]["current_values"]
    asyncio.run(verify.read_sources("test", CLAIMS, []))
    schema = json.loads(route.calls[-1].request.content)["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["current_values"]["maxItems"] == 0


@pytest.mark.parametrize("left,right,same", [(10, ["10"], True), (["10", "20"], 10, False), (None, [], False)])
def test_currency_compares_scalar_and_list_without_crashing(left, right, same):
    assert verify._same(left, right) is same


def test_investigator_records_provider_failure_and_cap_reason(http, monkeypatch):
    warnings = []
    async def warn(stage, reason):
        warnings.append((stage, reason))
    http.post(CHAT).respond(401, json={"error": {"message": "private provider response"}})
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test", on_warning=warn)))
    assert inv.outcome == "not_found" and warnings[0][0] == "investigate"
    assert "authenticate" in warnings[0][1] and "private provider response" not in warnings[0][1]
    monkeypatch.setattr(settings, "investigate_max_steps", 1)
    happy(http)
    warnings.clear()
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test", on_warning=warn)))
    assert inv.outcome == "capped" and "tool-call cap" in warnings[0][1]


def test_no_tool_call_stops_and_secret_arguments_never_reach_trace(http):
    secret = settings.secret("nebius_api_key")
    sources(http)
    http.post(CHAT).mock(side_effect=[reply("search", {"query": "Maker " + secret}), reply(text="No answer.")])
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "not_found" and len(inv.steps) == 1
    assert secret not in inv.model_dump_json() and "***" in inv.model_dump_json()


def test_tool_cache_budget_and_429_backoff(http, monkeypatch):
    sleeps = []
    original = asyncio.sleep
    monkeypatch.setattr(tokenfactory.asyncio, "sleep", lambda n: sleeps.append(n) or original(0))
    route = http.post(CHAT).mock(side_effect=[httpx.Response(429), reply("finish", FINAL)])
    asyncio.run(tokenfactory.chat_tools("investigate", [], TOOLS))
    _, u = asyncio.run(tokenfactory.chat_tools("investigate", [], TOOLS))
    assert u.cached and u.finish_reason == "tool_calls" and len(route.calls) == 2 and sleeps == [1]
    monkeypatch.setattr(settings, "budget_usd_per_day", 0)
    with pytest.raises(budget.BudgetExceeded):
        asyncio.run(tokenfactory.chat_tools("investigate", [{"role": "user", "content": "new request"}], TOOLS))
    assert len(route.calls) == 2


def test_scripted_revision_prevents_investigation(http):
    sources(http)
    route = http.post(CHAT).mock(return_value=reply(text=json.dumps({"status": "unknown", "current_revision": "Rev B"})))
    _, _, _, _, inv = asyncio.run(verify.verify({**CASE, "manufacturer_domains": []}, CLAIMS))
    assert inv is None and len(route.calls) == 1


def test_accepted_document_uses_existing_comparison(http):
    http.post(tavily.API + "/search").respond(200, json={"results": []})
    http.post(tavily.API + "/extract").respond(200, json={"results": [{"url": URL, "raw_content": "Rev B"}]})
    http.post(CHAT).mock(side_effect=[reply(text='{"status":"unknown"}'), reply("extract", {"url": URL}),
                                      reply("finish", {**FINAL, "status": "unknown"}),
                                      reply(text='{"status":"unknown","current_revision":"Rev B"}')])
    findings, rows, usage, _, inv = asyncio.run(verify.verify(CASE, CLAIMS))
    assert inv.outcome == "found" and findings[0].id == "currency-newer" and rows[0].current == "Rev B"
    assert sum(u.task == "investigate" for u in usage) == 2


def test_mock_s4_streams_investigation_and_answer_key_cases_do_not(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "mock")
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    with respx.mock:
        run = asyncio.run(execute(Run([*all_cases(), "s4"], delay_ms=0)))
    assert not [e for e in run.events if e.stage == "error"]
    assert all(run.results[c].investigation is None for c in all_cases())
    inv = run.results["s4"].investigation
    assert inv.outcome == "found" and [s.tool for s in inv.steps] == ["search", "map", "extract", "finish"]
    assert len([e for e in run.events if e.stage == "investigate" and e.model == settings.model_verify]) == 4


def test_private_url_and_invalid_arguments_are_not_executed(http):
    http.post(CHAT).mock(side_effect=[reply("extract", {"url": "http://127.0.0.1/admin"}), reply("search", {"query": 42}), reply()])
    inv = asyncio.run(investigate(CASE, CLAIMS, WebClient("test")))
    assert inv.outcome == "not_found" and len(inv.steps) == 2 and all(s.credits == 0 for s in inv.steps)
    assert all(c.request.url.host == "api.tokenfactory.nebius.com" for c in http.calls)


def test_empty_fix_candidate_is_investigated_then_checked(http):
    original = "https://maker.test/old.pdf"
    http.post(tavily.API + "/search").respond(200, json={"results": [{"url": original, "title": "Product X"}]})
    http.post(tavily.API + "/extract").mock(side_effect=[
        httpx.Response(200, json={"results": []}),
        httpx.Response(200, json={"results": [{"url": URL, "raw_content": "Rev B. VOC 10 g/L."}]}),
    ])
    http.get(original).respond(404)
    cl = {"product": "X", "manufacturer": "Maker", "document_revision": "Rev B", "claims": [{
        "id": "voc", "product": "X", "manufacturer": "Maker", "property": "voc", "value": 10, "unit": "g/L",
        "page": 1, "quote": "VOC 10 g/L."}]}
    http.post(CHAT).mock(side_effect=[reply("extract", {"url": URL}), reply("finish", {**FINAL, "status": "unknown"}),
                                      reply(text=json.dumps(cl)), reply(text='{"status":"unknown"}'), reply()])
    case = {**CASE, "fixture": None, "title": "Sealant", "submittal": [{"role": "product_data"}]}
    reqs = [Requirement(id="voc", section="07 84 00", paragraph="", property="voc", operator="lte", value=250, text="VOC limit")]
    findings = [Finding(id="old", check="currency", verdict="outdated", severity="major", title="Old sheet")]
    investigations = []
    usage, credits = asyncio.run(fix.find_fixes(case, reqs, CLAIMS, findings, 1, 8, investigations=investigations))
    assert investigations[0].outcome == "found" and any(u.task == "investigate" for u in usage)
    candidate = findings[0].fix.candidates[0]
    assert candidate.source_url == URL and candidate.checks[0].ok is True
    assert not candidate.passes and credits <= 8  # candidate web check still needs its own evidence


def test_unquoted_duplicate_property_is_dropped():
    out = VerifyOut(status="unknown", current_values=[
        {"property": "voc", "value": 10, "quote": "VOC 10"},
        {"property": "voc", "value": 900, "quote": "invented"}])
    verify.gate(out, [{"url": URL, "raw_content": "VOC 10"}])
    assert [v.value for v in out.current_values] == [10]


@pytest.mark.parametrize("submitted_values,current_values", [([10, 20], [15]), ([10], [15, 25])])
def test_currency_does_not_choose_between_unqualified_alternatives(submitted_values, current_values):
    submitted = ClaimsOut(product="X", manufacturer="Maker", claims=[
        {"id": str(i), "product": "X", "manufacturer": "Maker", "property": "measurement", "value": v}
        for i, v in enumerate(submitted_values)])
    out = VerifyOut(status="unknown", current_values=[
        {"property": "measurement", "value": v, "quote": f"Measurement {v}"} for v in current_values])
    pages = [{"url": URL, "raw_content": " ".join(v.quote for v in out.current_values)}]
    confirmed = verify.gate(out, pages)
    findings, rows = verify.compare(submitted, out, confirmed, [], pages)
    assert not rows and findings[0].verdict == "unverified"


def test_web_cri_requires_a_cri_quote():
    out = VerifyOut(status="unknown", current_values=[{"property": "cri", "value": 80, "quote": "75 – 80 typical LPW"}])
    verify.gate(out, [{"url": URL, "raw_content": "75 – 80 typical LPW"}])
    assert not out.current_values


def test_uncomparable_web_values_still_trigger_investigation(http, monkeypatch):
    async def search(*args, **kwargs):
        return [{"url": URL}]
    async def extract(*args, **kwargs):
        return [{"url": URL, "raw_content": "Measurement 15 or 25"}]
    calls = []
    async def investigate_missing(*args, **kwargs):
        calls.append(True)
        return Investigation()
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    monkeypatch.setattr(verify, "investigate", investigate_missing)
    content = json.dumps({"status": "unknown", "current_values": [
        {"property": "measurement", "value": 15, "quote": "Measurement 15 or 25"}]})
    http.post(CHAT).mock(return_value=reply(text=content))
    submitted = ClaimsOut(product="X", manufacturer="Maker", claims=[
        {"id": str(v), "product": "X", "manufacturer": "Maker", "property": "measurement", "value": v}
        for v in (10, 20)])
    findings, rows, _, _, inv = asyncio.run(verify.verify(CASE, submitted))
    assert calls == [True] and inv is not None
    assert not rows and findings[0].verdict == "unverified"


def test_fix_query_uses_reviewed_requirement_semantics():
    req = Requirement(id="reviewed-row-123", section="07 84 00", paragraph="", property="t_rating_hr",
                      operator="eq_ref", value="f_rating_hr", text="Equal ratings")
    finding = Finding(id="failed-row", requirement_id=req.id, check="spec", verdict="fail", severity="critical", title="Unequal")
    query = fix._query("spec", {**CASE, "title": "Sealant, pipe through wall"}, CLAIMS, [finding], [req])
    assert "Temperature rating (T) equals Fire rating (F)" in query


def test_fix_warns_when_candidate_verification_does_not_fit_cap(monkeypatch):
    async def search(*args, **kwargs):
        return [{"url": URL, "title": "Product X"}]
    async def extract(*args, **kwargs):
        return [{"url": URL, "raw_content": "Product X data"}]
    warnings = []
    async def warn(stage, reason):
        warnings.append((stage, reason))
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    case = {**CASE, "title": "Sealant, wall", "submittal": []}
    finding = Finding(id="old", check="currency", verdict="outdated", severity="major", title="Old data")
    result, _, _ = asyncio.run(fix._fix(case, "currency", [finding], [], CLAIMS, 1, 0, on_warning=warn))
    assert not result.candidates and warnings == [("fix", "Fix credit cap reached before candidate verification")]


@pytest.mark.parametrize("reference_present,passes", [(False, False), (True, True)])
def test_fix_must_demonstrate_original_failed_requirement(monkeypatch, reference_present, passes):
    from api.schemas import Usage
    async def search(*args, **kwargs):
        return [{"url": URL, "title": "Product X"}]
    async def extract(*args, **kwargs):
        return [{"url": URL, "raw_content": "Product X measurement 10"}]
    async def claims(*args, **kwargs):
        values = [Claim(id="m", product="X", manufacturer="Maker", property="measurement", value=10)]
        if reference_present:
            values.append(values[0].model_copy(update={"id": "r", "property": "reference"}))
        return CLAIMS.model_copy(update={"claims": values}), Usage(task="extract_claims", tier="extract", model="test")
    async def current(*args, **kwargs):
        return [Finding(id="currency-current", check="currency", verdict="pass", severity="info", title="Current")], [], [], 0, None
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    monkeypatch.setattr(fix.extract, "extract_claims", claims)
    monkeypatch.setattr(fix.verify, "verify", current)
    case = {**CASE, "title": "Sealant, wall", "submittal": []}
    req = Requirement(id="failed-requirement", section="07 84 00", paragraph="", property="measurement",
                      operator="eq_ref", value="reference", text="Equal measurements")
    finding = Finding(id="failed", requirement_id=req.id, check="spec", verdict="fail", severity="critical", title="Unequal")
    result, _, _ = asyncio.run(fix._fix(case, "spec", [finding], [req], CLAIMS, 1, 10))
    assert result.candidates[0].passes is passes
    if not passes:
        assert any(c.ok is None and "failed requirement" in c.note for c in result.candidates[0].checks)


def test_source_selection_keeps_manufacturer_status_notice():
    docs = [{"url": f"https://maker.test/{n}.pdf"} for n in range(4)]
    notice = {"url": "https://news.maker.test/update", "title": "Product discontinuation notice"}
    unrelated = {"url": "https://other.test/discontinued", "title": "Discontinued"}
    selected = verify.source_urls([unrelated, *docs, notice, notice], ["maker.test"])
    assert selected == [docs[0]["url"], docs[1]["url"], notice["url"]]
    assert verify.source_urls([], ["maker.test"]) == []


def test_investigator_can_read_cached_source_with_zero_web_allowance(http, monkeypatch):
    from api import cache
    monkeypatch.setattr(settings, "investigate_credit_cap", 0)
    cache.put("tavily_extract", {"urls": [URL], "depth": "basic"}, [
        {"url": URL, "raw_content": "Rev B. Product X is still made."}])
    http.post(CHAT).mock(side_effect=[reply("extract", {"url": URL}), reply("finish", FINAL)])
    web = WebClient("test")
    inv = asyncio.run(investigate(CASE, CLAIMS, web))
    assert inv.outcome == "found" and web.credits == 0
    assert [s.tool for s in inv.steps] == ["extract", "finish"]


def test_verify_backfills_unreadable_sources_once(http, monkeypatch):
    urls = [f"https://maker.test/{n}.pdf" for n in range(4)]
    extracts = []
    async def search(*args, **kwargs):
        return [{"url": u} for u in urls]
    async def extract(self, requested):
        extracts.append(requested)
        return [{"url": urls[-1], "raw_content": "Product X Rev B"}] if urls[-1] in requested else []
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    http.post(CHAT).mock(return_value=reply(text='{"status":"unknown","current_revision":"Rev B"}'))
    findings, _, _, _, inv = asyncio.run(verify.verify(CASE, CLAIMS))
    assert extracts == [urls[:3], urls[3:]]
    assert findings[0].evidence[0].url == urls[-1] and inv is None


def test_current_product_fixes_skip_candidates_without_quoted_properties(monkeypatch):
    async def search(self, query, **kwargs):
        assert kwargs["include_domains"] == ["maker.test"]
        return [{"url": "https://unrelated.test/sensor.pdf"}]
    async def extract(self, urls):
        return [{"url": urls[0], "raw_content": "An unrelated sensor data sheet"}]
    async def claims(*args, **kwargs):
        from api.schemas import Usage
        return ClaimsOut(product="Sensor", manufacturer="Other", claims=[]), Usage(task="extract_claims", tier="extract", model="test")
    async def verify_candidate(*args, **kwargs):
        pytest.fail("A candidate without quoted properties must not consume verification or investigation calls")
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    monkeypatch.setattr(fix.extract, "extract_claims", claims)
    monkeypatch.setattr(fix.verify, "verify", verify_candidate)
    findings = [Finding(id="old", check="currency", verdict="outdated", severity="major", title="Old sheet")]
    case = {**CASE, "title": "Fixture", "submittal": [{"role": "product_data"}]}
    asyncio.run(fix.find_fixes(case, [], CLAIMS, findings, 3, 12))
    assert findings[0].fix.candidates == []


@pytest.mark.parametrize("value,quote,kept", [
    ("<2", "contains <250 g/L VOC", False),
    ("<2", "VOC <2 g/L", True),
    ("<2", "VOC 2 g/L", False),
    ("<=2", "VOC ≤2 g/L", True),
    (2, "VOC <2 g/L", False),
    (2, "VOC 20 g/L", False),
    (50000, "Life 50,000 hours", True),
    (0.75, "Thickness 3/4 in", True),
    (1.125, "Thickness 1-1/8 in", True),
    (["IESNA LM-79-08", "NEMA"], "Certified to US and Canadian safety standards.", False),
    (["astm e814", "ul1479"], "Tested to ASTM E 814 and UL-1479.", True),
    ("UL 1479", "Tested to UL 14790.", False),
    (None, "Not stated", False),
    ([], "Standards", False),
])
def test_web_value_must_match_numeric_quote(value, quote, kept):
    out = VerifyOut(status="unknown", current_values=[{"property": "measurement", "value": value, "quote": quote}])
    verify.gate(out, [{"url": URL, "raw_content": quote}])
    assert bool(out.current_values) is kept


def test_verify_retries_numeric_quote_mismatch_once(http, monkeypatch):
    source = "VOC limit <100 g/L. Measured VOC <5 g/L."
    async def search(*args, **kwargs):
        return [{"url": URL}]
    async def extract(*args, **kwargs):
        return [{"url": URL, "raw_content": source}]
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    def content(quote):
        return json.dumps({"status": "unknown", "current_values": [
            {"property": "voc", "value": "<5", "quote": quote}]})
    route = http.post(CHAT).mock(side_effect=[
        reply(text=content("VOC limit <100 g/L.")), reply(text=content("Measured VOC <5 g/L."))])
    submitted = CLAIMS.model_copy(update={"claims": [Claim(id="voc", product="Product X", manufacturer="Maker",
        property="voc", value=10, page=1, quote="VOC 10")]})
    findings, rows, usage, _, _ = asyncio.run(verify.verify(CASE, submitted))
    assert len(route.calls) == len(usage) == 2
    sent = json.loads(route.calls[1].request.content)
    assert "Value quote validation rejected" in sent["messages"][-1]["content"]
    assert rows[0].current == "<5" and findings[0].verdict == "outdated"


def test_verify_numeric_retry_still_drops_unsupported_value(http, monkeypatch):
    source = "Rev B. VOC limit <100 g/L."
    async def search(*args, **kwargs):
        return [{"url": URL}]
    async def extract(*args, **kwargs):
        return [{"url": URL, "raw_content": source}]
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    content = json.dumps({"status": "unknown", "current_revision": "Rev B", "current_values": [
        {"property": "voc", "value": "<5", "quote": source}]})
    route = http.post(CHAT).mock(side_effect=[reply(text=content), reply(text=content)])
    submitted = CLAIMS.model_copy(update={"claims": [Claim(id="voc", product="Product X", manufacturer="Maker",
        property="voc", value=10, page=1, quote="VOC 10")]})
    findings, rows, usage, _, _ = asyncio.run(verify.verify(CASE, submitted))
    assert len(route.calls) == len(usage) == 2
    assert not any(r.property == "voc" for r in rows) and findings[0].verdict == "note"
