"""Live providers, budget and demo safety, with the HTTP layer mocked by respx (no network, no real keys)."""

import asyncio
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pymupdf
import pytest
import respx
from pydantic import BaseModel, SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api import config, main  # noqa: E402
from api.config import settings  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402
from api.providers import AuthError, ProviderError, RateLimited, budget, tavily, tokenfactory  # noqa: E402

NEBIUS_KEY, TAVILY_KEY, ADMIN = "sk-nebius-test-0123456789", "tvly-test-0123456789", "admin-test-0123456789"
CHAT = settings.nebius_base_url + "chat/completions"


class Tiny(BaseModel):
    ok: bool


def reply(text='{"ok": true}'):
    return httpx.Response(200, json={
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}})


def err(status, msg):
    return httpx.Response(status, json={"error": {"message": msg}})


def formats(route):
    return [json.loads(c.request.content)["response_format"]["type"] for c in route.calls]


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "nebius_api_key", SecretStr(NEBIUS_KEY))
    monkeypatch.setattr(settings, "tavily_api_key", SecretStr(TAVILY_KEY))
    monkeypatch.setattr(settings, "admin_token", SecretStr(ADMIN))
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    sleeps = []
    real_sleep = asyncio.sleep
    monkeypatch.setattr(tokenfactory.asyncio, "sleep", lambda s: sleeps.append(s) or real_sleep(0))
    main._uploads_by_ip.clear()
    with respx.mock as mock:
        yield mock, sleeps


def chat():
    return asyncio.run(tokenfactory.chat("triage", [{"role": "user", "content": "hi"}], Tiny))


# ---------- Token Factory ----------

def test_falls_back_to_json_object_when_json_schema_rejected(live):
    route = live[0].post(CHAT).mock(side_effect=[err(400, "response_format json_schema is not supported"), reply()])
    obj, usage = chat()
    assert obj.ok and formats(route) == ["json_schema", "json_object"] and usage.format == "json_object"
    assert usage.model == settings.model_triage


@pytest.mark.parametrize("status,error", [(401, AuthError), (403, AuthError), (429, RateLimited)])
def test_no_fallback_on_auth_or_rate_limit(live, status, error):
    route = live[0].post(CHAT).mock(return_value=err(status, "nope"))
    with pytest.raises(error) as e:
        chat()
    assert set(formats(route)) == {"json_schema"}  # never retried as json_object
    assert len(route.calls) == (1 + tokenfactory.RATE_LIMIT_RETRIES if status == 429 else 1)
    assert NEBIUS_KEY not in str(e.value)


def test_rate_limit_backs_off_then_succeeds(live):
    route = live[0].post(CHAT).mock(side_effect=[err(429, "slow"), err(429, "slow"), reply()])
    chat()
    assert len(route.calls) == 3 and live[1] == [1, 2]


def test_other_400_is_not_swallowed(live):
    route = live[0].post(CHAT).mock(return_value=err(400, "max_tokens is too large"))
    with pytest.raises(ProviderError, match="max_tokens"):
        chat()
    assert formats(route) == ["json_schema"]


def test_spend_guards_stop_before_paying(live, monkeypatch):
    route = live[0].post(CHAT).mock(return_value=reply())
    monkeypatch.setattr(settings, "budget_usd_per_day", 0.001)  # below one call's worst case
    with pytest.raises(budget.BudgetExceeded, match="daily"):
        chat()
    monkeypatch.setattr(settings, "budget_usd_per_day", 2.0)
    monkeypatch.setattr(settings, "model_triage", "unpriced/model")
    with pytest.raises(ProviderError, match="No price"):
        chat()
    assert not route.calls


def test_cut_off_reply_is_not_retried(live):
    body = reply('{"ok": tr').json()
    body["choices"][0]["finish_reason"] = "length"
    route = live[0].post(CHAT).mock(return_value=httpx.Response(200, json=body))
    with pytest.raises(ProviderError, match="MAX_OUTPUT_TOKENS"):
        chat()
    assert len(route.calls) == 1 and json.loads(route.calls[0].request.content)["max_tokens"] == settings.max_output_tokens


def test_invalid_json_retried_once(live):
    route = live[0].post(CHAT).mock(side_effect=[reply('{"ok": "maybe"}'), reply()])
    assert chat()[0].ok and len(route.calls) == 2


# ---------- Nemotron 3 thinks by default ----------

def sent(route, i=0):
    return json.loads(route.calls[i].request.content)


def test_asks_for_no_thinking_by_default(live):
    route = live[0].post(CHAT).mock(return_value=reply())
    _, usage = chat()
    body = sent(route)
    assert body["reasoning_effort"] == "none" and body["chat_template_kwargs"] == {"enable_thinking": False}
    assert usage.thinking == "off" and usage.reasoning_tokens == 0


def test_thinking_on_sends_no_flags(live, monkeypatch):
    monkeypatch.setattr(settings, "thinking", "on")
    route = live[0].post(CHAT).mock(return_value=reply())
    _, usage = chat()
    assert "reasoning_effort" not in sent(route) and "chat_template_kwargs" not in sent(route) and usage.thinking == "on"


def test_rejected_no_think_field_is_dropped_and_retried(live):
    route = live[0].post(CHAT).mock(side_effect=[err(400, "Unrecognized request argument: chat_template_kwargs"), reply()])
    _, usage = chat()
    assert len(route.calls) == 2
    assert "chat_template_kwargs" in sent(route, 0) and "chat_template_kwargs" not in sent(route, 1)
    assert sent(route, 1)["reasoning_effort"] == "none" and formats(route) == ["json_schema", "json_schema"]
    assert usage.thinking == "off"


def test_both_no_think_fields_rejected_means_server_default(live):
    route = live[0].post(CHAT).mock(side_effect=[
        err(400, "reasoning_effort is not supported"), err(400, "chat_template_kwargs is not supported"), reply()])
    _, usage = chat()
    assert len(route.calls) == 3 and usage.thinking == "server-default"
    assert not ({"reasoning_effort", "chat_template_kwargs"} & set(sent(route, 2)))


@pytest.mark.parametrize("text", [
    '<think>\nis it ok? yes\n</think>\n{"ok": true}',
    'Here is the JSON you asked for:\n{"ok": true}\nLet me know if you need anything else.',
    '```json\n{"ok": true}\n```',
    '<think>reasoning</think>```json\n{"ok": true}\n```',
])
def test_json_is_read_around_thinking_and_prose(live, text):
    live[0].post(CHAT).mock(return_value=reply(text))
    assert chat()[0].ok


def test_reasoning_content_is_never_the_answer(live):
    body = reply('{"ok": true}').json()
    body["choices"][0]["message"]["reasoning_content"] = '{"ok": false}'
    body["usage"]["completion_tokens_details"] = {"reasoning_tokens": 57}
    live[0].post(CHAT).mock(return_value=httpx.Response(200, json=body))
    obj, usage = chat()
    assert obj.ok and usage.reasoning_tokens == 57


def test_cut_off_while_thinking_retries_with_thinking_off(live, monkeypatch):
    monkeypatch.setattr(settings, "thinking", "on")
    cut = reply('').json()
    cut["choices"][0]["finish_reason"] = "length"
    cut["usage"]["completion_tokens_details"] = {"reasoning_tokens": 8192}
    route = live[0].post(CHAT).mock(side_effect=[httpx.Response(200, json=cut), reply()])
    obj, usage = chat()
    assert obj.ok and len(route.calls) == 2 and usage.thinking == "off"
    assert "reasoning_effort" not in sent(route, 0) and sent(route, 1)["reasoning_effort"] == "none"


def test_cut_off_with_thinking_already_off_fails_once(live):
    cut = reply('{"ok": tr').json()
    cut["choices"][0]["finish_reason"] = "length"
    route = live[0].post(CHAT).mock(return_value=httpx.Response(200, json=cut))
    with pytest.raises(ProviderError, match="MAX_OUTPUT_TOKENS"):
        chat()
    assert len(route.calls) == 1


def test_list_models(live):
    live[0].get(settings.nebius_base_url + "models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]}))
    assert asyncio.run(tokenfactory.list_models()) == ["a", "b"]


@pytest.mark.parametrize("enabled,count,arguments", [
    (False, 0, '{}'), (True, 1, '{"model_number":"SPK-100"}'),
    (True, 2, '{"model_number":"SPK-100"}'), (True, 1, 'invalid'), (True, 0, '{}'),
])
def test_spike_models_tools_flag(live, monkeypatch, capsys, enabled, count, arguments):
    monkeypatch.setenv("SPECCHECK_MODE", "mock")
    from scripts import spike_models

    monkeypatch.setattr(sys, "argv", ["spike_models.py", "--yes", *(["--tools"] if enabled else [])])
    live[0].get(settings.nebius_base_url + "models").respond(200, json={
        "data": [{"id": m} for m in set(settings.models.values())]})

    def respond(request):
        body = json.loads(request.content)
        if "tools" not in body:
            return reply('{"product":"sealant","f_rating_hours":2,"standard":"ASTM E814"}')
        assert "response_format" not in body and body["model"] == settings.model_verify
        assert body["tools"][0]["function"]["name"] == "lookup"
        assert body["tools"][0]["function"]["parameters"]["required"] == ["model_number"]
        return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls" if count else "stop", "message": {
            "role": "assistant", "tool_calls": [{"id": f"call-{i}", "type": "function", "function": {
                "name": "lookup", "arguments": arguments}} for i in range(count)]}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                      "completion_tokens_details": {"reasoning_tokens": 7}}})

    route = live[0].post(CHAT).mock(side_effect=respond)
    asyncio.run(spike_models.main())
    output = capsys.readouterr().out
    assert len(route.calls) == (3 if enabled else 2)
    if enabled:
        assert f"tool_calls={bool(count)}  count={count}" in output
        assert f"finish_reason={'tool_calls' if count else 'stop'}" in output
        assert f"arguments_json={bool(count) and arguments != 'invalid'}" in output
        assert f"multiple_calls={count > 1}" in output and "reasoning_tokens=7" in output
    else:
        assert "== tools:" not in output


def test_cache_hit_makes_no_call(live):
    route = live[0].post(CHAT).mock(return_value=reply())
    _, first = chat()
    _, second = chat()
    assert len(route.calls) == 1 and not first.cached and second.cached
    cached = "".join(p.read_text() for p in settings.cache_dir.rglob("*.json"))
    assert NEBIUS_KEY not in cached


def test_cost_is_charged_and_logged(live, monkeypatch, caplog):
    monkeypatch.setitem(config.PRICES, settings.model_triage, (1.0, 2.0))
    live[0].post(CHAT).mock(return_value=reply())
    led = budget.Ledger()
    budget.LEDGER.set(led)
    try:
        with caplog.at_level(logging.INFO, "speccheck"):
            _, usage = chat()
    finally:
        budget.LEDGER.set(None)
    assert usage.cost_usd == pytest.approx((10 * 1 + 3 * 2) / 1e6) and led.usd == usage.cost_usd
    assert budget.today()["usd"] == usage.cost_usd and "in=10 out=3" in caplog.text


# ---------- Tavily ----------

def test_credit_math():
    assert [tavily.search_credits("basic"), tavily.search_credits("advanced")] == [1, 2]
    assert [tavily.extract_credits(n) for n in (1, 5, 6, 10, 11)] == [1, 1, 2, 2, 3]
    assert tavily.extract_credits(6, "advanced") == 4
    assert [tavily.map_credits(n) for n in (0, 10, 11, 20)] == [1, 1, 2, 2]
    assert tavily.map_credits(20, "only PDFs") == 4


def test_tavily_charges_caches_and_caps(live, monkeypatch):
    mock = live[0]
    search = mock.post(f"{tavily.API}/search").mock(return_value=httpx.Response(200, json={"results": [{"url": "https://a.test"}]}))
    mp = mock.post(f"{tavily.API}/map").mock(return_value=httpx.Response(200, json={"results": [f"https://a.test/{i}" for i in range(500)]}))
    ext = mock.post(f"{tavily.API}/extract").mock(return_value=httpx.Response(200, json={"results": [{"url": "https://a.test/1", "raw_content": "x"}]}))
    mock.get("https://a.test/2").mock(return_value=httpx.Response(200, content=b"<html>not a pdf</html>"))
    led = budget.Ledger()
    budget.LEDGER.set(led)
    budget.ITEM.set("c01")
    try:
        assert asyncio.run(tavily.search("q", depth="advanced"))[1] == 2
        assert asyncio.run(tavily.search("q", depth="advanced"))[1] == 0  # cache hit
        links, spent = asyncio.run(tavily.map("https://a.test"))
        assert len(links) == 20 and spent == 2 and json.loads(mp.calls[0].request.content)["limit"] == 20
        pages, spent = asyncio.run(tavily.extract(["https://a.test/1", "https://a.test/2"]))
        assert [p["url"] for p in pages] == ["https://a.test/1"] and spent == 1  # failed URL free, not-a-PDF dropped
        assert led.credits == {"c01": 5} and budget.today()["credits"] == 5
        assert search.calls[0].request.headers["authorization"] == f"Bearer {TAVILY_KEY}" and len(ext.calls) == 1

        monkeypatch.setattr(settings, "budget_tavily_credits_per_item", 6)
        with pytest.raises(budget.BudgetExceeded):
            asyncio.run(tavily.search("other", depth="advanced"))  # 5 + 2 > 6, refused before the call
        assert len(search.calls) == 1
    finally:
        budget.LEDGER.set(None)
        budget.ITEM.set("")


def test_tavily_401_is_typed(live):
    live[0].post(f"{tavily.API}/search").mock(return_value=httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(AuthError):
        asyncio.run(tavily.search("q"))


def test_tavily_reported_usage_overrides_credit_estimates(live):
    mock = live[0]
    search = mock.post(f"{tavily.API}/search").respond(200, json={"results": [], "usage": {"credits": 3}})
    extract = mock.post(f"{tavily.API}/extract").respond(200, json={"results": [], "usage": {"credits": 1}})
    mp = mock.post(f"{tavily.API}/map").respond(200, json={"results": ["https://a.test/1"], "usage": {"credits": 0}})
    mock.get("https://a.test/1").respond(403)
    led_token = budget.LEDGER.set(budget.Ledger())
    item_token = budget.ITEM.set("test")
    try:
        assert asyncio.run(tavily.search("usage"))[1] == 3
        assert asyncio.run(tavily.extract(["https://a.test/1"]))[1] == 1  # failed URL can still be billed
        assert asyncio.run(tavily.map("https://a.test"))[1] == 0  # reported zero must remain zero
        assert budget.today()["credits"] == 4
        assert asyncio.run(tavily.extract(["https://a.test/1"]))[1] == 0
        assert len(extract.calls) == 1
        assert all(json.loads(r.calls[0].request.content)["include_usage"] for r in (search, extract, mp))
    finally:
        budget.LEDGER.reset(led_token)
        budget.ITEM.reset(item_token)


def test_fetch_pdf_keeps_only_pdfs(live):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "FS-ONE MAX data sheet")
    live[0].get("https://m.test/a.pdf").mock(return_value=httpx.Response(200, content=doc.tobytes()))
    live[0].get("https://m.test/b.pdf").mock(return_value=httpx.Response(200, content=b"<html>Cloudflare</html>"))
    pages = asyncio.run(tavily.fetch_pdf("https://m.test/a.pdf"))
    assert "FS-ONE MAX" in pages[0]["text"]
    assert asyncio.run(tavily.fetch_pdf("https://m.test/b.pdf")) is None
    assert live[0].calls[0].request.headers["user-agent"].startswith("Mozilla/5.0")


def test_document_discovery_uses_public_links_and_resolves_relative_urls():
    html = '<a href="http://127.0.0.1/private.pdf">Bad</a><a href="/docs/current.pdf">Spec</a>'
    assert tavily._document_link(html, "https://maker.test/product") == "https://maker.test/docs/current.pdf"
    assert tavily._document_link('"https://cdn.test/PDS_Product_English"', "https://maker.test") == "https://cdn.test/PDS_Product_English"


def test_product_page_extract_resolves_linked_pdf_and_keeps_its_url(live):
    page, document = "https://maker.test/product", "https://cdn.test/PDS_Product_English"
    route = live[0].post(f"{tavily.API}/extract").respond(200, json={
        "results": [{"url": page, "raw_content": "Product Data Sheet"}], "usage": {"credits": 1}})
    html = live[0].get(page).respond(200, text=f'<a href="{document}">Product Data Sheet</a>')
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Manufacturer product data sheet, Revision C")
    pdf = live[0].get(document).respond(200, content=doc.tobytes())
    pages, spent = asyncio.run(tavily.extract([page]))
    assert pages[0]["url"] == document and pages[0]["requested_url"] == page
    assert "Revision C" in pages[0]["raw_content"] and spent == 1
    cached, charged = asyncio.run(tavily.extract([page]))
    assert charged == 0 and cached == [{**p, "cache_hit": True} for p in pages]
    assert len(route.calls) == len(html.calls) == len(pdf.calls) == 1


def test_failed_linked_pdf_probe_is_not_repeated_on_cache_hit(live):
    page = "https://maker.test/product"
    post = live[0].post(tavily.API + "/extract").respond(200, json={
        "results": [{"url": page, "raw_content": "Product data sheet"}]})
    direct = live[0].get(page).respond(403)
    first, _ = asyncio.run(tavily.extract([page]))
    second, spent = asyncio.run(tavily.extract([page]))
    assert second == [{**p, "cache_hit": True} for p in first] and first[0]["raw_content"] == "Product data sheet"
    assert spent == 0 and len(post.calls) == len(direct.calls) == 1


@pytest.mark.parametrize("legacy_checked", [False, True])
def test_blocked_product_page_follows_link_through_tavily_once(live, legacy_checked):
    from api import cache
    page, document = "https://maker.test/product", "https://maker.test/current.pdf"
    stamp = datetime.now(timezone.utc).isoformat()
    cache.put("tavily_extract", {"urls": [page], "depth": "basic"}, {
        "version": 1, "retrieved_at": stamp, "results": [{"url": page,
            "raw_content": "[Spec sheet](/current.pdf)", "document_checked": legacy_checked}]})
    direct = live[0].get(page).respond(403)
    post = live[0].post(tavily.API + "/extract").respond(200, json={"usage": {"credits": 2},
        "results": [{"url": document, "raw_content": "Actual data sheet. [Other](/another.pdf)"}]})
    pages, spent = asyncio.run(tavily.extract([page]))
    assert spent == 2 and [p["url"] for p in pages] == [page, document]
    assert pages[0]["retrieved_at"] == stamp and pages[1]["requested_url"] == page
    assert pages[1]["cache_hit"] is False
    cached, spent = asyncio.run(tavily.extract([page]))
    assert spent == 0 and cached == [{**p, "cache_hit": True} for p in pages]
    assert len(post.calls) == 1 and len(direct.calls) == (0 if legacy_checked else 1)
    assert json.loads(post.calls[0].request.content)["urls"] == [document]
    assert len(cache.get("tavily_extract", {"urls": [page], "depth": "basic"})["results"]) == 1


def test_linked_pdf_negative_cache_expires_independently(live):
    from api import cache
    from datetime import timedelta
    page, document = "https://maker.test/product", "https://maker.test/blocked.pdf"
    live[0].get(page).respond(403)
    live[0].get(document).respond(403)
    def respond(request):
        requested = json.loads(request.content)["urls"]
        return httpx.Response(200, json={"results": ([{"url": page,
            "raw_content": "[Data](/blocked.pdf)"}] if requested == [page] else []), "usage": {"credits": 1}})
    post = live[0].post(tavily.API + "/extract").mock(side_effect=respond)
    assert asyncio.run(tavily.extract([page]))[1] == 2
    assert asyncio.run(tavily.extract([page]))[1] == 0
    key = {"urls": [document], "depth": "basic"}
    entry = cache.get("tavily_extract", key)
    entry["retrieved_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    cache.put("tavily_extract", key, entry)
    assert asyncio.run(tavily.extract([page]))[1] == 1
    assert len(post.calls) == 3


def test_linked_pdf_provider_failure_is_not_silently_hidden(live):
    page = "https://maker.test/product"
    live[0].get(page).respond(403)
    live[0].post(tavily.API + "/extract").mock(side_effect=[httpx.Response(200, json={
        "results": [{"url": page, "raw_content": "[Data](/blocked.pdf)"}], "usage": {"credits": 1}}),
        httpx.Response(429)])
    with pytest.raises(RateLimited):
        asyncio.run(tavily.extract([page]))


def test_direct_pdf_lookup_has_total_timeout(live, monkeypatch):
    real_timeout = asyncio.timeout
    monkeypatch.setattr(tavily.asyncio, "timeout", lambda _: real_timeout(0))
    async def delayed(request):
        await asyncio.sleep(0.01)
        return httpx.Response(200, content=b"%PDF-invalid")
    live[0].get(URL := "https://maker.test/slow.pdf").mock(side_effect=delayed)
    assert asyncio.run(tavily.fetch_pdf(URL)) is None


@pytest.mark.parametrize("cached", [False, True])
def test_raw_pdf_syntax_is_replaced_with_direct_text_or_dropped(live, cached):
    from api import cache
    urls = ["https://m.test/good.pdf", "https://m.test/blocked.pdf"]
    raw = [{"url": u, "raw_content": "%PDF-1.7 1 0 obj xref gibberish"} for u in urls]
    route = live[0].post(f"{tavily.API}/extract").respond(200, json={"results": raw, "usage": {"credits": 1}})
    if cached:
        cache.put("tavily_extract", {"urls": sorted(urls), "depth": "basic"}, {
            "version": 1, "retrieved_at": datetime.now(timezone.utc).isoformat(), "results": raw})
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Readable current product data, Rev C")
    live[0].get(urls[0]).respond(200, content=doc.tobytes())
    live[0].get(urls[1]).respond(403)
    pages, spent = asyncio.run(tavily.extract(urls))
    assert [p["url"] for p in pages] == [urls[0]] and "Rev C" in pages[0]["raw_content"]
    assert spent == (0 if cached else 1) and len(route.calls) == (0 if cached else 1)
    assert asyncio.run(tavily.extract(urls))[0] == [{**p, "cache_hit": True} for p in pages]
    assert tavily._pdf_syntax("binary fragment\nstartxref\n116\n%%EOF")


# ---------- budget in the pipeline (mock mode) ----------

def test_budget_exceeded_marks_step_couldnt_confirm(monkeypatch):
    monkeypatch.setattr(settings, "budget_tavily_credits_per_item", 0)
    run = asyncio.run(execute(Run(["c01", "c03"], delay_ms=0)))
    assert not [e for e in run.events if e.stage == "error"]  # the run finished every item
    for cid in ("c01", "c03"):
        f = next(f for f in run.results[cid].findings if f.check == "currency")
        assert f.verdict == "unverified" and f.title == "Couldn't confirm the current documents" and "Tavily cap" in f.detail
        assert any("verify:" in warning and "Tavily cap" in warning for warning in run.results[cid].warnings)
        assert any(e.case_id == cid and e.stage == "verify" and (e.data or {}).get("warning") for e in run.events)
    shutil.rmtree(run.dir, ignore_errors=True)


def test_usd_cap_stops_model_calls(monkeypatch):
    monkeypatch.setattr(settings, "budget_usd_per_run", 0)
    run = asyncio.run(execute(Run(["c01"], delay_ms=0)))
    assert "run budget" in next(e.message for e in run.events if e.stage == "error")
    shutil.rmtree(run.dir, ignore_errors=True)


# ---------- config and startup ----------

def test_live_without_keys_fails_at_startup_naming_the_variable():
    assert config.check_startup(config.Settings(_env_file=None)).mode == "mock"  # mock needs no keys
    with pytest.raises(config.MissingKey, match="NEBIUS_API_KEY, TAVILY_API_KEY"):
        config.check_startup(config.Settings(_env_file=None, speccheck_mode="live"))
    with pytest.raises(config.MissingKey) as e:
        config.check_startup(config.Settings(_env_file=None, speccheck_mode="live", nebius_api_key=NEBIUS_KEY))
    assert "TAVILY_API_KEY" in str(e.value) and "NEBIUS_API_KEY" not in str(e.value) and NEBIUS_KEY not in str(e.value)


def test_access_logs_keep_formatter_fields_and_redact_keys(live):
    from uvicorn.logging import AccessFormatter

    record = logging.getLogger("uvicorn.access").makeRecord("uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:8000", "GET", f"/api/test?key={NEBIUS_KEY}", "1.1", 200), None)
    text = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False).format(record)
    assert NEBIUS_KEY not in text and "/api/test?key=***" in text and "200 OK" in text


def test_logs_are_redacted(live, caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("anything").info("key=%s header=Bearer %s admin=%s", NEBIUS_KEY, "tvly-otherkey123456", ADMIN)  # gitleaks:allow (fake key)
    assert NEBIUS_KEY not in caplog.text and "tvly-otherkey123456" not in caplog.text and ADMIN not in caplog.text
    assert "Bearer ***" in caplog.text


# ---------- API ----------

client = TestClient(main.app)


@pytest.fixture(scope="module", autouse=True)
def client_lifespan():
    with client:
        yield


def test_health_never_leaks_a_key(live):
    r = client.get("/api/health")
    body = r.text
    for k in (NEBIUS_KEY, TAVILY_KEY, ADMIN):
        assert k not in body
    h = r.json()
    assert h["mode"] == "live" and h["keys"]["NEBIUS_API_KEY"] is True and set(h["keys"]) == {"NEBIUS_API_KEY", "TAVILY_API_KEY", "ADMIN_TOKEN"}
    assert h["models"]["triage"] == settings.model_triage and set(h["today"]) == {"usd", "credits"}


def _pdf_bytes():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "LED troffer 4000 lumens, luminaire data")
    return doc.tobytes()


def test_live_without_token_runs_are_refused_and_uploads_can_opt_out(live, monkeypatch):
    monkeypatch.setattr(settings, "public_uploads_live", False)
    assert client.post("/api/runs", json={"case_ids": ["c01"]}).status_code == 403
    assert client.post("/api/scores/run").status_code == 403
    assert client.post("/api/runs", json={"case_ids": ["nope"]}, headers={"x-admin-token": "wrong"}).status_code == 403

    case = client.post("/api/inbox?name=mine.pdf", content=_pdf_bytes()).json()
    r = client.post("/api/scan", json={"ids": [case["id"]], "delay_ms": 0})
    up = r.json()
    try:
        assert r.status_code == 200 and up["mock"] == [case["id"]] and "admin token" in up["note"]
        t0 = time.time()
        while (res := client.get(f"/api/runs/{up['run_id']}/results/{case['id']}")).status_code != 200:
            assert time.time() - t0 < 10
            time.sleep(0.05)
        assert "Mock mode" in res.json()["summary"]
        assert not live[0].calls  # nothing went to Token Factory or Tavily
    finally:
        shutil.rmtree(settings.uploads_dir / case["id"], ignore_errors=True)


def test_upload_rejects_non_pdf_big_files_and_floods(live, monkeypatch):
    assert client.post("/api/inbox?name=x.pdf", content=b"hello").status_code == 400
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert client.post("/api/inbox?name=x.pdf", content=_pdf_bytes()).status_code == 413
    monkeypatch.setattr(settings, "uploads_per_ip_per_hour", 2)
    main._uploads_by_ip.clear()
    monkeypatch.setattr(settings, "max_upload_mb", 15)
    codes = [client.post("/api/inbox?name=x.pdf", content=b"x" * 10).status_code for _ in range(3)]
    assert codes == [400, 400, 429]
