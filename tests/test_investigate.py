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
from api.pipeline.investigate import TOOLS, investigate
from api.pipeline.runner import Run, execute
from api.providers import budget, tavily, tokenfactory
from api.schemas import ClaimsOut, Finding, Requirement, VerifyOut
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
    assert u.cached and len(route.calls) == 2 and sleeps == [1]
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
