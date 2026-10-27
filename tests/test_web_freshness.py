import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import respx

from api import cache
from api.config import settings
from api.providers import budget, tavily
from api.web import WebClient

URL = "https://maker.test/sheet.pdf"
KEY = {"urls": [URL], "depth": "basic"}


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "speccheck_mode", "live")


@pytest.mark.parametrize("hours,results,expected_calls", [
    (23, [{"url": URL, "raw_content": "Earlier document"}], 0),
    (25, [{"url": URL, "raw_content": "Earlier document"}], 1),
    (0.5, [], 0), (2, [], 1),
])
def test_positive_and_negative_cache_expiry(live, hours, results, expected_calls):
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cache.put("tavily_extract", KEY, {"version": 1, "retrieved_at": stamp, "results": results})
    with respx.mock as http:
        route = http.post(tavily.API + "/extract").respond(200, json={
            "results": [{"url": URL, "raw_content": "Fresh document"}], "usage": {"credits": 1}})
        found = asyncio.run(WebClient(None).extract([URL]))
    assert len(route.calls) == expected_calls
    if found and not expected_calls:
        assert found[0]["retrieved_at"] == stamp and found[0]["cache_hit"] is True
    if expected_calls:
        assert found[0]["raw_content"] == "Fresh document" and found[0]["cache_hit"] is False


def test_explicit_refresh_and_legacy_unknown_age_do_not_reuse_old_text(live):
    cache.put("tavily_extract", KEY, [{"url": URL, "raw_content": "Unknown-age document"}])
    with respx.mock as http:
        route = http.post(tavily.API + "/extract").respond(200, json={
            "results": [{"url": URL, "raw_content": "Fresh document"}], "usage": {"credits": 1}})
        asyncio.run(WebClient(None).extract([URL]))
        token = cache.REFRESH_WEB.set(True)
        try:
            asyncio.run(WebClient(None).extract([URL]))
        finally:
            cache.REFRESH_WEB.reset(token)
    assert len(route.calls) == 2


def test_failed_refresh_does_not_renew_cached_evidence(live):
    from api.providers import ProviderError
    stamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    original = {"version": 1, "retrieved_at": stamp, "results": [{"url": URL, "raw_content": "Old document"}]}
    cache.put("tavily_extract", KEY, original)
    with respx.mock as http:
        http.post(tavily.API + "/extract").respond(503)
        with pytest.raises(ProviderError):
            asyncio.run(WebClient(None).extract([URL]))
    assert cache.get("tavily_extract", KEY) == original
