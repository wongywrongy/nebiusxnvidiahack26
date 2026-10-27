from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
import sqlite3

import httpx
import pytest
import respx
from pydantic import BaseModel, SecretStr

from api.config import settings
from api.providers import campaign, budget, tokenfactory, tavily, ProviderError
from api.providers.budget import BudgetExceeded

pytestmark = pytest.mark.campaign


@pytest.fixture
def campaign_state(tmp_path, monkeypatch):
    path = tmp_path / "campaign.sqlite3"
    campaign.initialize(path, campaign.Amount(usd_nano=1058605000, credits=298),
        {"2026-10-21": campaign.Amount(usd_nano=1048778000, credits=291), "2026-10-22": campaign.Amount(usd_nano=9827000, credits=7)},
        campaign.Amount(usd_nano=20000000000, credits=2000), campaign.Amount(usd_nano=10000000000, credits=1000))
    monkeypatch.setattr(settings, "campaign_budget_file", path)
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    monkeypatch.setattr(settings, "nebius_api_key", SecretStr("test-campaign-model"))
    monkeypatch.setattr(settings, "tavily_api_key", SecretStr("test-campaign-web"))
    lt, it = budget.LEDGER.set(budget.Ledger("campaign-test")), budget.ITEM.set("item")
    yield path
    budget.LEDGER.reset(lt)
    budget.ITEM.reset(it)


def reserve(path, usd=100000000, credits=0, **kwargs):
    return campaign.reserve(path, campaign.Amount(usd_nano=usd, credits=credits), **{
        "run": "run", "item": "item", "run_usd_nano": 3000000000, "day_usd_nano": 20000000000,
        "item_credits": 60, "day_credits": 2000, "scopes": [], **kwargs})


def test_historical_seed_and_engineering_allocation_are_durable(campaign_state):
    ticket = reserve(campaign_state)
    report, applied = campaign.settle(campaign_state, ticket, campaign.Amount(usd_nano=25000000))
    assert applied
    assert report["total_usd"] == 1.083605 and report["phase_usd"] == 0.025
    assert campaign.settle(campaign_state, ticket, campaign.Amount(usd_nano=25000000)) == (report, False)
    with pytest.raises(BudgetExceeded, match="Conflicting"):
        campaign.settle(campaign_state, ticket, campaign.Amount(usd_nano=30000000))
    with pytest.raises(FileExistsError):
        campaign.initialize(campaign_state, campaign.Amount(), {}, campaign.Amount(), campaign.Amount())


def test_concurrent_requests_include_outstanding_holds(campaign_state):
    def attempt(_):
        try:
            return reserve(campaign_state, usd=1800000000)
        except BudgetExceeded:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(r is not None for r in results) == 1


def test_pending_payment_still_protects_next_day_cap(campaign_state, monkeypatch):
    from datetime import datetime, timezone
    class Clock:
        day = "2026-10-24"
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(cls.day).replace(tzinfo=timezone.utc)
    monkeypatch.setattr(campaign, "datetime", Clock)
    # Keep provenance validation on the real date parser.
    Clock.fromisoformat = datetime.fromisoformat
    ticket = reserve(campaign_state, usd=1800000000)
    Clock.day = "2026-10-25"
    assert campaign.status(campaign_state)["held_usd"] == 1.8
    with pytest.raises(BudgetExceeded):
        reserve(campaign_state, usd=400000000, run="next-run", day_usd_nano=2000000000)
    campaign.settle(campaign_state, ticket, campaign.Amount(usd_nano=10000000))
    assert reserve(campaign_state, usd=400000000, run="next-run", day_usd_nano=2000000000)


def test_unknown_settlement_blocks_paid_work_after_restart(campaign_state):
    ticket = reserve(campaign_state)
    report, _ = campaign.settle(campaign_state, ticket, None)
    assert report["held_usd"] == 0.1 and report["blocked"]
    with pytest.raises(BudgetExceeded, match="reconciliation"):
        reserve(campaign_state)
    campaign.settle(campaign_state, ticket, campaign.Amount())
    assert reserve(campaign_state)


def test_owner_resolve_hold_command(campaign_state, monkeypatch, capsys):
    from scripts.campaign_budget import cli
    ticket = reserve(campaign_state, usd=0, credits=1)
    campaign.settle(campaign_state, ticket, None)
    monkeypatch.setattr("sys.argv", ["campaign_budget.py", "resolve-hold", ticket, "--credits", "1", "--usd", "0"])
    cli()
    result = json.loads(capsys.readouterr().out)
    assert result["id"] == ticket
    assert result["before"]["held_credits"] == 1 and result["before"]["blocked"]
    assert result["after"]["held_credits"] == 0 and not result["after"]["blocked"]
    assert result["after"]["total_credits"] == result["before"]["total_credits"]
    assert result["after"]["total_usd"] == result["before"]["total_usd"]
    for identifier in (ticket, "missing"):
        monkeypatch.setattr("sys.argv", ["campaign_budget.py", "resolve-hold", identifier, "--credits", "1", "--usd", "0"])
        with pytest.raises(SystemExit, match="No unresolved hold"):
            cli()
        assert campaign.status(campaign_state) == result["after"]
    assert reserve(campaign_state)


def test_item_and_nested_credit_limits_include_holds(campaign_state):
    reserve(campaign_state, usd=0, credits=40)
    with pytest.raises(BudgetExceeded):
        reserve(campaign_state, usd=0, credits=21)
    scopes = [{"id": "scope", "cap": 5, "spent": 0}]
    reserve(campaign_state, usd=0, credits=4, item="other", scopes=scopes)
    with pytest.raises(BudgetExceeded, match="step cap"):
        reserve(campaign_state, usd=0, credits=2, item="another", scopes=scopes)


def test_missing_or_corrupt_ledger_cannot_initialize_zero(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(BudgetExceeded, match="accounting unavailable"):
        reserve(path)
    assert not path.exists()
    path.write_text("damaged")
    with pytest.raises(BudgetExceeded, match="accounting unavailable"):
        reserve(path)


def test_usage_above_reserved_maximum_records_actual_then_blocks(campaign_state):
    ticket = reserve(campaign_state, usd=10000000)
    report, _ = campaign.settle(campaign_state, ticket, campaign.Amount(usd_nano=20000000))
    assert report["total_usd"] == 1.078605 and report["blocked"]
    with pytest.raises(BudgetExceeded):
        reserve(campaign_state)


def test_corrupt_money_types_and_inconsistent_seed_fail_closed(campaign_state):
    with sqlite3.connect(campaign_state) as conn:
        conn.execute("UPDATE campaign SET data=replace(data, '1058605000', '-1058605000')")
    with pytest.raises(BudgetExceeded):
        reserve(campaign_state)


def test_process_restart_cannot_forget_an_inflight_reservation(campaign_state, monkeypatch):
    reserve(campaign_state)
    monkeypatch.setattr(campaign, "SESSION", "restarted")
    assert campaign.status(campaign_state)["blocked"]
    with pytest.raises(BudgetExceeded, match="reconciliation"):
        reserve(campaign_state)


class Answer(BaseModel):
    ok: bool


def response(text='{"ok":true}', *, usage=True):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        **({"usage": {"prompt_tokens": 100, "completion_tokens": 20}} if usage else {})})


def test_invalid_json_retry_and_cache_settle_every_paid_attempt(campaign_state):
    opening_usd = campaign.status(campaign_state)["usd"]
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=[response('invalid'), response()])
        _, usage = asyncio.run(tokenfactory.chat("triage", [], Answer))
        asyncio.run(tokenfactory.chat("triage", [], Answer))
    assert len(route.calls) == 2
    assert budget.LEDGER.get().fresh_usd["item"] == pytest.approx(2 * usage.cost_usd)
    with campaign.transaction(campaign_state) as state:
        assert len(state.payments) == 2 and all(p.actual is not None for p in state.payments.values())
    assert json.loads(budget._day_file().read_text())["usd"] == pytest.approx(opening_usd + 2 * usage.cost_usd)


def test_missing_usage_retains_hold_and_cached_reply_stays_invalid(campaign_state):
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(return_value=response(usage=False))
        asyncio.run(tokenfactory.chat("triage", [], Answer))
        budget.LEDGER.get().accounting_issues.clear()
        asyncio.run(tokenfactory.chat("triage", [], Answer))
        assert budget.LEDGER.get().accounting_issues["item"]
        with pytest.raises(BudgetExceeded):
            asyncio.run(tokenfactory.chat("triage", [{"role": "user", "content": "different"}], Answer))
    report = campaign.status(campaign_state)
    assert report["blocked"] and report["held_usd"] > 0 and len(route.calls) == 1


def test_429_cannot_start_another_paid_attempt_with_unknown_billing(campaign_state, monkeypatch):
    sleep = asyncio.sleep
    monkeypatch.setattr(tokenfactory.asyncio, "sleep", lambda _: sleep(0))
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=[httpx.Response(429), response()])
        with pytest.raises(BudgetExceeded, match="reconciliation"):
            asyncio.run(tokenfactory.chat("triage", [], Answer))
    assert len(route.calls) == 1
    assert any("429" in message for message in budget.LEDGER.get().accounting_issues["item"])


def test_reported_tavily_usage_is_settled_before_malformed_results(campaign_state):
    opening_credits = campaign.status(campaign_state)["credits"]
    with respx.mock as http:
        http.post(tavily.API + "/extract").respond(200, json={"usage": {"credits": 3}, "results": None})
        with pytest.raises(TypeError):
            asyncio.run(tavily.extract(["https://maker.test/sheet.pdf"]))
    report = campaign.status(campaign_state)
    assert report["credits"] == opening_credits + 3 and report["blocked"]  # Above the request's one-credit bound.
    assert budget.LEDGER.get().fresh_credits["item"] == 3


def test_failed_extract_is_zero_cost_and_does_not_erase_other_holds(campaign_state):
    opening_credits = campaign.status(campaign_state)["credits"]
    with respx.mock as http:
        http.post(tavily.API + "/extract").respond(503)
        with pytest.raises(ProviderError):
            asyncio.run(tavily.extract(["https://maker.test/sheet.pdf"]))
    report = campaign.status(campaign_state)
    assert not report["blocked"] and report["credits"] == opening_credits and report["held_credits"] == 0


def test_concurrent_http_admission_reserves_before_network(campaign_state, monkeypatch):
    monkeypatch.setattr(settings, "budget_usd_per_run", 0.02)
    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow(request):
            entered.set()
            await release.wait()
            return response()
        with respx.mock as http:
            route = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=slow)
            body = {"model": settings.model_triage, "max_tokens": 32, "messages": []}
            first = asyncio.create_task(tokenfactory._request("POST", "/chat/completions", body))
            await entered.wait()
            with pytest.raises(BudgetExceeded):
                await tokenfactory._request("POST", "/chat/completions", body)
            release.set()
            await first
            assert len(route.calls) == 1
    asyncio.run(check())


def test_missing_wallet_or_item_sends_no_http(campaign_state, monkeypatch):
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(return_value=response())
        it = budget.ITEM.set("")
        try:
            with pytest.raises(BudgetExceeded):
                asyncio.run(tokenfactory.chat("triage", [], Answer))
        finally:
            budget.ITEM.reset(it)
        monkeypatch.setattr(settings, "campaign_budget_file", campaign_state.parent / "absent.sqlite3")
        with pytest.raises(BudgetExceeded):
            asyncio.run(tokenfactory.chat("triage", [], Answer))
    assert not route.calls


def test_duplicate_settlement_charges_ledger_and_nested_scope_once(campaign_state):
    with budget.credit_scope(10):
        ticket = budget.reserve_payment(usd=0.1, credits=4)
        budget.settle_payment(ticket, usd=0.02, credits=3)
        budget.settle_payment(ticket, usd=0.02, credits=3)
        assert budget._CREDIT_SCOPES.get()[0]["spent"] == 3
    led = budget.LEDGER.get()
    assert led.usd == 0.02 and led.fresh_usd["item"] == 0.02
    assert led.credits["item"] == led.fresh_credits["item"] == 3
    with pytest.raises(campaign.SettlementConflict):
        budget.settle_payment(ticket, usd=0.04, credits=3)
    assert led.usd == 0.02


def test_settlement_write_failure_keeps_known_usage_and_blocks_new_paid_work(campaign_state, monkeypatch):
    ticket = budget.reserve_payment(usd=0.1)
    transaction = campaign.transaction
    def broken(_):
        raise OSError("disk unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(campaign, "transaction", broken)
        with pytest.raises(OSError):
            budget.settle_payment(ticket, usd=0.02)
    assert campaign.status(campaign_state)["blocked"]
    with pytest.raises(BudgetExceeded, match="settlement"):
        budget.reserve_payment(usd=0.1)
    assert budget.LEDGER.get().fresh_usd["item"] == 0.02
    with pytest.raises(campaign.SettlementConflict):
        budget.settle_payment(ticket, usd=0.03)
    with campaign.transaction(campaign_state) as state:
        assert state.payments[ticket].actual is None
    budget.settle_payment(ticket, usd=0.02)
    assert not campaign.status(campaign_state)["blocked"]
    assert budget.LEDGER.get().fresh_usd["item"] == 0.02


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("timed out"), asyncio.CancelledError()])
def test_network_failure_or_cancellation_retains_unknown_hold(campaign_state, failure):
    attempts = []
    async def fail(request):
        attempts.append(request.url.path)
        raise failure
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=fail)
        with pytest.raises((ProviderError, asyncio.CancelledError)):
            asyncio.run(tokenfactory.chat("triage", [], Answer))
    assert len(attempts) == 1
    report = campaign.status(campaign_state)
    assert report["blocked"] and report["held_usd"] > 0


def test_priced_but_unbounded_model_is_rejected_before_http(campaign_state, monkeypatch):
    monkeypatch.setitem(tokenfactory.PRICES, "nvidia/unknown", (0.01, 0.01))
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(return_value=response())
        with pytest.raises(ProviderError, match="bound"):
            asyncio.run(tokenfactory._request("POST", "/chat/completions", {"model": "nvidia/unknown", "max_tokens": 10}))
    assert not route.calls


def test_explicit_initialization_reads_only_selected_reconciled_days(tmp_path, monkeypatch):
    from scripts.campaign_budget import initialize
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    monkeypatch.setattr(settings, "campaign_budget_file", tmp_path / "new.sqlite3")
    days = tmp_path / "budget"
    days.mkdir()
    (days / "2026-10-21.json").write_text('{"usd":1.048778,"credits":291.0}')
    (days / "2026-10-22.json").write_text('{"usd":0.009827,"credits":7.0}')
    (days / "2026-10-08.json").write_text('{"usd":9,"credits":900}')
    result = initialize(["2026-10-21", "2026-10-22"])
    assert result["total_usd"] == 1.058605 and result["total_credits"] == 298
    with pytest.raises(FileExistsError):
        initialize(["2026-10-21", "2026-10-22"])


def test_reported_rejected_request_usage_and_format_retry_are_both_settled(campaign_state):
    rejected = httpx.Response(400, json={"error": {"message": "response_format json_schema unsupported"},
                                        "usage": {"prompt_tokens": 10, "completion_tokens": 0}})
    with respx.mock as http:
        route = http.post(settings.nebius_base_url + "chat/completions").mock(side_effect=[rejected, response()])
        _, usage = asyncio.run(tokenfactory.chat("triage", [], Answer))
    assert len(route.calls) == 2 and usage.format == "json_object"
    assert budget.LEDGER.get().fresh_usd["item"] == pytest.approx(usage.cost_usd + tokenfactory.cost(settings.model_triage, 10, 0))
    with campaign.transaction(campaign_state) as state:
        assert len(state.payments) == 2 and all(p.actual is not None for p in state.payments.values())


def test_day_rollover_does_not_move_an_inflight_charge(campaign_state, monkeypatch):
    from datetime import datetime, timezone
    class DayOne:
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 22, 23, 59, tzinfo=timezone.utc)
        fromisoformat = datetime.fromisoformat
    class DayTwo(DayOne):
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 23, 0, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(campaign, "datetime", DayOne)
    ticket = reserve(campaign_state)
    monkeypatch.setattr(campaign, "datetime", DayTwo)
    report, _ = campaign.settle(campaign_state, ticket, campaign.Amount(usd_nano=20000000))
    assert report["day"] == "2026-10-22" and report["usd"] == 0.029827
    assert campaign.status(campaign_state)["usd"] == 0


def test_engineering_credit_allocation_cannot_consume_final_reserve(campaign_state):
    for n in range(10):
        ticket = reserve(campaign_state, usd=0, credits=100, item=f"item-{n}", item_credits=100)
        campaign.settle(campaign_state, ticket, campaign.Amount(credits=100))
    with pytest.raises(BudgetExceeded, match="allocation"):
        reserve(campaign_state, usd=0, credits=1, item="last")
    report = campaign.status(campaign_state)
    assert report["phase_credits"] == 1000 and report["total_credits"] == 1298
    assert "campaign allocation" in budget.unavailable_reason()


def test_unavailable_accounting_does_not_tell_people_to_wait_for_midnight(campaign_state, monkeypatch):
    monkeypatch.setattr(settings, "campaign_budget_file", campaign_state.parent / "missing.sqlite3")
    assert budget.day_spent()
    assert "accounting" in budget.unavailable_reason() and "tomorrow" not in budget.unavailable_reason()
