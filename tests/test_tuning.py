import asyncio
import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from api.config import Settings, settings
from api.llm import router
from api.pipeline import extract, metrics, verify
from api.pipeline.runner import Run, execute
from api.pipeline.scores import scores
from api.providers import budget, tavily
from api.schemas import ClaimsOut, ToolMessage, VerifyOut
from api.web import WebClient


class Answer(BaseModel):
    value: int


@respx.mock
def test_per_task_thinking_changes_both_request_and_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "thinking_tasks", " verify, investigate ")
    structured = {"choices": [{"message": {"content": '{"value":1}'}}]}
    route = respx.post(settings.nebius_base_url + "chat/completions").respond(200, json=structured)
    for task in ("verify", "extract_claims", "verify"):
        asyncio.run(router.call(task, Answer, [{"role": "user", "content": "same input"}]))
    assert len(route.calls) == 2
    first, second = [json.loads(c.request.content) for c in route.calls]
    assert "reasoning_effort" not in first and "chat_template_kwargs" not in first
    assert second["reasoning_effort"] == "none" and second["chat_template_kwargs"] == {"enable_thinking": False}
    route.respond(200, json={"choices": [{"message": {"role": "assistant", "tool_calls": []}}]})
    asyncio.run(router.call("investigate", ToolMessage, [], {"tools": []}))
    asyncio.run(router.call("investigate", ToolMessage, [], {"tools": []}))
    assert len(route.calls) == 3
    monkeypatch.setattr(settings, "thinking_tasks", "")
    asyncio.run(router.call("investigate", ToolMessage, [], {"tools": []}))
    assert len(route.calls) == 4
    on, off = [json.loads(c.request.content) for c in route.calls[-2:]]
    assert "response_format" not in on and "response_format" not in off
    assert "reasoning_effort" not in on and off["reasoning_effort"] == "none"


@respx.mock
def test_depth_and_result_count_reach_web_provider_and_mock_cost(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "search_depth", "advanced")
    monkeypatch.setattr(settings, "extract_depth", "advanced")
    monkeypatch.setattr(settings, "search_max_results", 1)
    async def lookups():
        web = WebClient("c01")
        found = await web.search("test")
        await web.extract([found[0]["url"]])
        return found, web.credits
    found, credits = asyncio.run(lookups())
    assert len(found) == 1 and credits == 4
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    search = respx.post(tavily.API + "/search").respond(200, json={"results": [{"url": "https://maker.test/a"}]})
    fetch = respx.post(tavily.API + "/extract").respond(200, json={"results": [{"url": "https://maker.test/a", "raw_content": "source"}]})
    assert asyncio.run(lookups())[1] == 4
    sent = json.loads(search.calls[0].request.content)
    assert sent["search_depth"] == "advanced" and sent["max_results"] == 1
    assert json.loads(fetch.calls[0].request.content)["extract_depth"] == "advanced"


def test_text_limits_do_not_truncate_quote_gate_and_counts_drop_unquoted_values(monkeypatch):
    monkeypatch.setattr(settings, "max_page_chars", 5)
    monkeypatch.setattr(settings, "web_source_chars", 6)
    prompts = {}
    async def call(task, schema, messages, ctx):
        from api.schemas import Usage
        prompts[task] = messages[0]["content"]
        usage = Usage(task=task, tier="extract", model=settings.model_extract)
        if task == "extract_claims":
            return ClaimsOut(product="test", manufacturer="maker", claims=[
                {"id": str(i), "product": "test", "manufacturer": "maker", "property": "voc", "value": 1, "page": 1, "quote": quote}
                for i, quote in enumerate(("a quote past the excerpt: 1", "invented quote"))]), usage
        return VerifyOut(status="unknown", current_values=[
            {"property": "voc", "value": 1, "quote": quote} for quote in ("a quote past the excerpt: 1", "invented quote")]), usage
    monkeypatch.setattr(router, "call", call)
    counts = dict.fromkeys(metrics.FIELDS, 0)
    token = metrics.COUNTS.set(counts)
    pages = [{"page": 1, "text": "prefix a quote past the excerpt: 1"}]
    sources = [{"url": "https://maker.test", "raw_content": pages[0]["text"]}]
    try:
        claims, _ = asyncio.run(extract.extract_claims("test", pages, extract.all_product_data(pages), ["voc"]))
        out, _ = asyncio.run(verify.read_sources("test", claims, sources))
        verify.gate(out, sources)
        verify.gate(out, sources, measure=False)
    finally:
        metrics.COUNTS.reset(token)
    assert counts == dict(claims_extracted=2, claims_kept=1, web_values_read=2, web_values_kept=1)
    assert len(claims.claims) == len(out.current_values) == 1
    assert '"text": "prefi"' in prompts["extract_claims"]
    assert '"text": "prefix"' in prompts["verify"]


def test_investigation_knobs_cap_tool_calls_and_credits(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    monkeypatch.setattr(settings, "investigate_max_steps", 1)
    run = asyncio.run(execute(Run(["s4"], delay_ms=0)))
    inv = run.results["s4"].investigation
    assert inv.outcome == "capped" and len(inv.steps) == 1
    monkeypatch.setattr(settings, "investigate_max_steps", 6)
    monkeypatch.setattr(settings, "investigate_credit_cap", 0)
    run = asyncio.run(execute(Run(["s4"], delay_ms=0)))
    inv = run.results["s4"].investigation
    assert inv.outcome == "capped" and sum(s.credits for s in inv.steps) == 0


def test_result_counts_aggregate_without_cross_item_leakage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    run = asyncio.run(execute(Run(["c01", "c03"], delay_ms=0)))
    single = asyncio.run(execute(Run(["c01"], delay_ms=0)))
    score = scores(run, run.case_ids)
    for key in metrics.FIELDS:
        assert getattr(run.results["c01"], key) == getattr(single.results["c01"], key)
        assert score["quote_gate"][key] == sum(getattr(r, key) for r in run.results.values())
    assert score["quote_gate"]["claims_extracted"] > 0
    assert score["tuning"]["web_source_chars"] == 12000


@pytest.mark.parametrize("field,value", [("search_depth", "other"), ("extract_depth", "other"),
                                        ("search_max_results", 0), ("max_page_chars", 0), ("investigate_max_steps", 0)])
def test_invalid_tuning_is_rejected(field, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{field: value})
