"""Tests never spend provider tokens or credits, even if a developer's .env selects live mode."""

import os
import json
import math
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import respx

os.environ["SPECCHECK_MODE"] = "mock"


def pytest_configure(config):
    config.addinivalue_line("markers", "campaign: exercise the real durable payment allocator")
    config.addinivalue_line("markers", "unreported_usage: retain intentionally incomplete provider usage")


@pytest.fixture(autouse=True)
def protocol_billing_fixtures(request, monkeypatch, tmp_path):
    """Legacy protocol tests use isolated payment doubles; campaign tests exercise durable admission."""
    if request.node.get_closest_marker("campaign"):
        return
    from api.config import settings
    from api.providers import budget, campaign
    monkeypatch.setattr(settings, 'cache_dir', tmp_path / 'protocol-cache')
    monkeypatch.setattr(settings, 'campaign_budget_file', tmp_path / 'protocol.sqlite3')
    payments = {}
    def reserve(path, held, **kwargs):
        identifier = uuid.uuid4().hex
        payments[identifier] = SimpleNamespace(held=held, actual=None, unknown=False, owner=campaign.SESSION, kind='request')
        return identifier
    @contextmanager
    def transaction(_):
        yield SimpleNamespace(payments=payments)
    def status(_):
        path = budget._day_file()
        return json.loads(path.read_text()) if path.exists() else {"usd": 0.0, "credits": 0}
    def settle(_, identifier, actual):
        current = status(None)
        return {"day": datetime.now(timezone.utc).date().isoformat(),
                "usd": round(current["usd"] + (actual.usd_nano / 1e9 if actual else 0), 9),
                "credits": current["credits"] + (actual.credits if actual else 0), "blocked": actual is None}, True
    monkeypatch.setattr(campaign, "reserve", reserve)
    monkeypatch.setattr(campaign, "transaction", transaction)
    monkeypatch.setattr(campaign, "settle", settle)
    monkeypatch.setattr(campaign, "status", status)
    if request.node.get_closest_marker("unreported_usage"):
        return
    original = httpx.AsyncClient.request
    async def reported_response(client, method, url, **kwargs):
        response = await original(client, method, url, **kwargs)
        if response.status_code != 200:
            return response
        try:
            payload = response.json()
        except ValueError:
            return response
        if not isinstance(payload, dict) or "usage" in payload:
            return response
        body = kwargs.get("json") or {}
        if str(url).startswith(settings.nebius_base_url.rstrip("/")) and "choices" in payload:
            payload["usage"] = {"prompt_tokens": 1, "completion_tokens": 1}
        elif str(url).startswith("https://api.tavily.com") and "results" in payload:
            results = payload["results"] or []
            n = (2 if body.get("search_depth") == "advanced" else 1) if str(url).endswith("/search") else (
                math.ceil(len(results) / 5) * (2 if body.get("extract_depth") == "advanced" else 1)
                if str(url).endswith("/extract") else max(1, math.ceil(min(len(results), body.get("limit", 20)) / 10)) * (2 if body.get("instructions") else 1))
            payload["usage"] = {"credits": n}
        else:
            return response
        return httpx.Response(response.status_code, json=payload, request=response.request)
    monkeypatch.setattr(httpx.AsyncClient, "request", reported_response)


@pytest.fixture(autouse=True)
def no_provider_network():
    with respx.mock(assert_all_called=False):
        yield
