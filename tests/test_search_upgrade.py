"""Tavily request options, cache separation and the single map fallback, with HTTP intercepted."""

import asyncio
import json

import httpx
import pytest
import respx

from api.config import settings
from api.pipeline import verify
from api.providers import ProviderError, budget, tavily
from api.schemas import ClaimsOut


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    token = budget.LEDGER.set(budget.Ledger())
    item = budget.ITEM.set("search-test")
    with respx.mock(assert_all_called=False) as http:
        yield http
    budget.ITEM.reset(item)
    budget.LEDGER.reset(token)


def test_search_options_and_dates_are_preserved_in_cache(live):
    route = live.post(tavily.API + "/search").respond(200, json={"results": [{"url": "https://maker.test/pdf", "published_date": "2026-10-01"}]})
    opts = dict(include_domains=["maker.test"], include_domains_mode="prefer", topic="news", include_published_date=True, exact_match=True)
    first, spent = asyncio.run(tavily.search('Maker "X-1" discontinued', **opts))
    assert spent == 1 and first[0]["published_date"] == "2026-10-01"
    assert asyncio.run(tavily.search('Maker "X-1" discontinued', **opts))[1] == 0
    asyncio.run(tavily.search('Maker "X-1" discontinued', **{**opts, "exact_match": False}))
    assert len(route.calls) == 2
    sent = json.loads(route.calls[0].request.content)
    assert all(sent[k] == v for k, v in opts.items())


def test_domain_mode_is_omitted_without_domains_and_400_is_not_retried(live):
    route = live.post(tavily.API + "/search").mock(side_effect=[httpx.Response(200, json={"results": []}), httpx.Response(400, text="bad request")])
    asyncio.run(tavily.search("query", include_domains_mode="prefer"))
    assert "include_domains_mode" not in json.loads(route.calls[0].request.content)
    with pytest.raises(ProviderError, match="400"):
        asyncio.run(tavily.search("other query", include_domains=["maker.test"], include_domains_mode="prefer"))
    assert len(route.calls) == 2 and budget.today()["credits"] == 1


def test_map_once_before_investigator_and_same_quote_comparison(live):
    url = "https://maker.test/X-1.pdf"
    search = live.post(tavily.API + "/search").respond(200, json={"results": []})
    mapped = live.post(tavily.API + "/map").respond(200, json={"results": [url]})
    extract = live.post(tavily.API + "/extract").respond(200, json={"results": [{"url": url, "raw_content": "Maker X-1 Rev B."}]})
    model = live.post(settings.nebius_base_url + "chat/completions").respond(200, json={"choices": [{"message": {"content": json.dumps({"status": "unknown", "current_revision": "Rev B"})}}]})
    findings, _, _, credits, inv = asyncio.run(verify.verify({"id": "map-test", "manufacturer_domains": ["maker.test"]},
        ClaimsOut(product="Product", manufacturer="Maker", model="X-1", document_revision="Rev A", claims=[])))
    assert inv is None and any(f.verdict == "note" for f in findings)
    assert len(mapped.calls) == len(extract.calls) == len(model.calls) == 1 and credits == 7
    assert len(search.calls) == 4
    args = json.loads(mapped.calls[0].request.content)
    assert args["limit"] == 20 and args["max_depth"] == 1
    query = json.loads(search.calls[2].request.content)
    assert query["topic"] == "news" and query["exact_match"] and '"X-1"' in query["query"]


def test_general_only_discontinuation_is_found_and_urls_deduplicated(live):
    url = "https://maker.test/notice.pdf"
    def search_reply(request):
        body = json.loads(request.content)
        hits = [{"url": url}] * 2 if body["topic"] == "general" and " OR " in body["query"] else []
        return httpx.Response(200, json={"results": hits})
    search = live.post(tavily.API + "/search").mock(side_effect=search_reply)
    extracted = live.post(tavily.API + "/extract").respond(200, json={"results": [
        {"url": url, "raw_content": "Maker X-1 is discontinued."}]})
    live.post(settings.nebius_base_url + "chat/completions").respond(200, json={"choices": [{"message": {
        "content": json.dumps({"status": "discontinued", "status_quote": "X-1 is discontinued."})}}]})
    findings, _, _, credits, _ = asyncio.run(verify.verify({"id": "general-test", "manufacturer_domains": ["maker.test"]},
        ClaimsOut(product="Product", manufacturer="Maker", model="X-1", claims=[])))
    assert any(f.id == "status-discontinued" for f in findings)
    bodies = [json.loads(c.request.content) for c in search.calls]
    assert len(bodies) == 4 and [b["topic"] for b in bodies[1:3]] == ["general", "news"]
    assert all(b["include_published_date"] and b["exact_match"] for b in bodies[1:3])
    assert bodies[3]["query"] == "Maker Product discontinuation notice"
    assert bodies[3]["include_domains"] == ["maker.test"] and bodies[3]["include_domains_mode"] == "prefer"
    assert json.loads(extracted.calls[0].request.content)["urls"] == [url]
    assert credits == budget.today()["credits"] == 5
