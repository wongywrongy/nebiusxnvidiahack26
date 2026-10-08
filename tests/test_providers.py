"""Live providers, budget and demo safety, with the HTTP layer mocked by respx (no network, no real keys)."""

import asyncio
import json
import logging
import shutil
import sys
import time
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


def test_list_models(live):
    live[0].get(settings.nebius_base_url + "models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]}))
    assert asyncio.run(tokenfactory.list_models()) == ["a", "b"]


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


def test_fetch_pdf_keeps_only_pdfs(live):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "FS-ONE MAX data sheet")
    live[0].get("https://m.test/a.pdf").mock(return_value=httpx.Response(200, content=doc.tobytes()))
    live[0].get("https://m.test/b.pdf").mock(return_value=httpx.Response(200, content=b"<html>Cloudflare</html>"))
    pages = asyncio.run(tavily.fetch_pdf("https://m.test/a.pdf"))
    assert "FS-ONE MAX" in pages[0]["text"]
    assert asyncio.run(tavily.fetch_pdf("https://m.test/b.pdf")) is None
    assert live[0].calls[0].request.headers["user-agent"].startswith("Mozilla/5.0")


# ---------- budget in the pipeline (mock mode) ----------

def test_budget_exceeded_marks_step_couldnt_confirm(monkeypatch):
    monkeypatch.setattr(settings, "budget_tavily_credits_per_item", 0)
    run = asyncio.run(execute(Run(["c01", "c03"], delay_ms=0)))
    assert not [e for e in run.events if e.stage == "error"]  # the run finished every item
    for cid in ("c01", "c03"):
        f = next(f for f in run.results[cid].findings if f.check == "currency")
        assert f.verdict == "unverified" and f.title == "Couldn't confirm the current documents" and "Tavily cap" in f.detail
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


def test_logs_are_redacted(live, caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("anything").info("key=%s header=Bearer %s admin=%s", NEBIUS_KEY, "tvly-otherkey123456", ADMIN)  # gitleaks:allow (fake key)
    assert NEBIUS_KEY not in caplog.text and "tvly-otherkey123456" not in caplog.text and ADMIN not in caplog.text
    assert "Bearer ***" in caplog.text


# ---------- API ----------

client = TestClient(main.app)


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


def test_live_without_token_runs_are_refused_and_uploads_go_to_mock(live):
    assert client.post("/api/runs", json={"case_ids": ["c01"]}).status_code == 403
    assert client.post("/api/scores/run").status_code == 403
    assert client.post("/api/runs", json={"case_ids": ["nope"]}, headers={"x-admin-token": "wrong"}).status_code == 403

    r = client.post("/api/uploads?name=mine.pdf&delay_ms=0", content=_pdf_bytes())
    up = r.json()
    try:
        assert r.status_code == 200 and up["mode"] == "mock" and "admin token" in up["note"]
        t0 = time.time()
        while (res := client.get(f"/api/runs/{up['run_id']}/results/{up['case']['id']}")).status_code != 200:
            assert time.time() - t0 < 10
            time.sleep(0.05)
        assert "Mock mode" in res.json()["summary"]
        assert not live[0].calls  # nothing went to Token Factory or Tavily
    finally:
        shutil.rmtree(settings.uploads_dir / up["case"]["id"], ignore_errors=True)


def test_upload_rejects_non_pdf_big_files_and_floods(live, monkeypatch):
    assert client.post("/api/uploads?name=x.pdf", content=b"hello").status_code == 400
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert client.post("/api/uploads?name=x.pdf", content=_pdf_bytes()).status_code == 413
    monkeypatch.setattr(settings, "uploads_per_ip_per_hour", 2)
    main._uploads_by_ip.clear()
    monkeypatch.setattr(settings, "max_upload_mb", 15)
    codes = [client.post("/api/uploads?name=x.pdf", content=b"x" * 10).status_code for _ in range(3)]
    assert codes == [400, 400, 429]
