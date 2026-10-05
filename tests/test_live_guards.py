"""Live-path guards, with the OpenAI and Tavily clients faked: format fallback, 429 backoff, map cap."""

import asyncio
import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import llm, web  # noqa: E402


class Tiny(BaseModel):
    ok: bool


def _err(cls, status, msg):
    resp = httpx.Response(status, request=httpx.Request("POST", "http://test"))
    return cls(msg, response=resp, body=None)


def _reply(text='{"ok": true}'):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
                           usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3))


class FakeCompletions:
    """Raises the queued errors in order, then replies. Records the response_format of every call."""

    def __init__(self, *errors):
        self.errors = list(errors)
        self.formats = []

    async def create(self, **kw):
        self.formats.append(kw["response_format"]["type"])
        if self.errors:
            raise self.errors.pop(0)
        return _reply()


@pytest.fixture
def router(monkeypatch):
    monkeypatch.setattr(llm.cache, "get", lambda *a: None)
    monkeypatch.setattr(llm.cache, "put", lambda *a: None)
    real_sleep = asyncio.sleep
    r = llm.Router()
    r.sleeps = []
    monkeypatch.setattr(llm.asyncio, "sleep", lambda s: r.sleeps.append(s) or real_sleep(0))

    def use(fake):
        r._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
        return r

    return use


def _live(r):
    return asyncio.run(r._live("triage", "nano", Tiny, [{"role": "user", "content": "hi"}]))


def test_falls_back_when_server_rejects_response_format(router):
    fake = FakeCompletions(_err(openai.BadRequestError, 400, "response_format json_schema is not supported"))
    obj, usage = _live(router(fake))
    assert obj.ok and fake.formats == ["json_schema", "json_object"]
    assert usage.format == "json_object"


def test_json_schema_recorded_when_it_works(router):
    _, usage = _live(router(FakeCompletions()))
    assert usage.format == "json_schema"


@pytest.mark.parametrize("error", [
    _err(openai.AuthenticationError, 401, "invalid api key"),
    _err(openai.BadRequestError, 400, "max_tokens is too large"),
])
def test_other_errors_are_not_swallowed(router, error):
    fake = FakeCompletions(error)
    with pytest.raises(type(error)):
        _live(router(fake))
    assert fake.formats == ["json_schema"]


def test_rate_limit_backs_off_then_gives_up(router):
    fake = FakeCompletions(*[_err(openai.RateLimitError, 429, "slow down")] * 2)
    r = router(fake)
    _, usage = _live(r)
    assert len(fake.formats) == 3 and usage.format == "json_schema"
    assert r.sleeps == [1, 2]

    fake = FakeCompletions(*[_err(openai.RateLimitError, 429, "slow down")] * 4)
    with pytest.raises(openai.RateLimitError):
        _live(router(fake))
    assert len(fake.formats) == 1 + llm.RATE_LIMIT_RETRIES


def test_map_is_capped(monkeypatch):
    monkeypatch.setattr(web, "settings", dataclasses.replace(web.settings, mode="live"))
    monkeypatch.setattr(web.cache, "get", lambda *a: None)
    monkeypatch.setattr(web.cache, "put", lambda *a: None)
    calls = []

    class FakeTavily:
        async def map(self, **kw):
            calls.append(kw)
            return {"results": [f"https://x.test/{i}" for i in range(500)]}  # server ignoring the limit

    client = web.WebClient("t")
    client._tavily = FakeTavily()
    links = asyncio.run(client.map("https://x.test"))
    assert calls[0]["limit"] == 20 and calls[0]["max_depth"] == 1
    assert len(links) == 20 and client.credits == 2 == web.map_credits(20)
