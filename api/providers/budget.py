"""Spend ledger: USD per run and per day, Tavily credits per item and per day.

The runner opens a Ledger per run (LEDGER) and names the item it is working on (ITEM); both are
context variables, so concurrent items each see their own. Providers check before a call and
charge after it. A cap raises BudgetExceeded; the runner turns that into a "couldn't confirm" step.
Live requests reserve against campaign SQLite before HTTP; .cache/budget/<date>.json is a report mirror.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from decimal import Decimal, ROUND_CEILING
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from ..config import settings


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self.usd = 0.0
        self.credits: dict[str, float] = {}  # item id -> Tavily credits
        self.investigation_credits: dict[str, float] = {}
        self.fresh_usd: dict[str, float] = {}
        self.fresh_credits: dict[str, float] = {}
        self.accounting_issues: dict[str, list[str]] = {}
        self.accounted_payments: dict[str, tuple[int, int]] = {}


def unknown_usage(reason: str) -> None:
    if led := LEDGER.get():
        issues = led.accounting_issues.setdefault(ITEM.get(), [])
        if reason not in issues:
            issues.append(reason)


LEDGER: ContextVar[Optional[Ledger]] = ContextVar("ledger", default=None)
ITEM: ContextVar[str] = ContextVar("item", default="")
_CREDIT_SCOPES: ContextVar[tuple] = ContextVar("credit_scopes", default=())


@contextmanager
def credit_scope(cap: float):
    """Nested loop caps, checked by every web call, including candidate verification."""
    token = _CREDIT_SCOPES.set((*_CREDIT_SCOPES.get(), {"id": uuid.uuid4().hex, "spent": 0.0, "cap": max(0, cap)}))
    try:
        yield
    finally:
        _CREDIT_SCOPES.reset(token)


def _day_file():
    return settings.cache_dir / "budget" / f"{datetime.now(timezone.utc).date()}.json"


def today() -> dict:
    if settings.live:
        from . import campaign
        try:
            return campaign.status(settings.campaign_budget_file)
        except BudgetExceeded:
            return {"usd": None, "credits": None, "blocked": True, "accounting_available": False}
    p = _day_file()
    return json.loads(p.read_text()) if p.exists() else {"usd": 0.0, "credits": 0.0}


def remaining() -> dict:
    spent = today()
    if spent.get("blocked"):
        return {"usd_left": 0.0, "credits_left": 0.0}
    if "total_usd" in spent:
        return {"usd_left": max(0, min(settings.budget_usd_per_day - spent["usd"] - spent["held_usd"],
                                      spent["usd_limit"] - spent["total_usd"], spent["phase_usd_limit"] - spent["phase_usd"])),
                "credits_left": max(0, min(settings.budget_tavily_credits_per_day - spent["credits"] - spent["held_credits"],
                                          spent["credit_limit"] - spent["total_credits"], spent["phase_credit_limit"] - spent["phase_credits"]))}
    return {"usd_left": max(0, settings.budget_usd_per_day - spent["usd"]),
            "credits_left": max(0, settings.budget_tavily_credits_per_day - spent["credits"])}


def caps() -> dict:
    return {key: getattr(settings, key) for key in (
        "budget_usd_per_run", "budget_usd_per_day", "budget_tavily_credits_per_item",
        "budget_tavily_credits_per_day", "max_concurrency")}


def day_spent() -> bool:
    return any(left <= 0 for left in remaining().values())


def unavailable_reason() -> str:
    spent = today()
    if spent.get("blocked"):
        return "Live checks are paused because campaign accounting needs owner reconciliation."
    if "phase_usd" in spent and (spent["phase_usd"] >= spent["phase_usd_limit"] or spent["phase_credits"] >= spent["phase_credit_limit"]):
        return "The live campaign allocation is spent; ask the owner to review the allowance."
    return "Today's live budget is spent. Try again tomorrow (UTC)."


def _add_today(usd: float = 0.0, credits: float = 0.0) -> None:
    # ponytail: read-modify-write with no lock, fine for one worker; use a DB row if we run several.
    p = _day_file()
    t = json.loads(p.read_text()) if p.exists() else {"usd": 0.0, "credits": 0.0}
    t = {"usd": round(t["usd"] + usd, 6), "credits": t["credits"] + credits}
    p = _day_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(t))


def check_usd(worst: float = 0.0, real: bool = False) -> None:
    """Before a model call: raise if its worst-case cost would cross the run cap, or (real) today's cap."""
    led = LEDGER.get()
    spent = sum(led.fresh_usd.values()) if led and real else led.usd if led else 0
    if led and (spent >= settings.budget_usd_per_run or spent + worst > settings.budget_usd_per_run):
        raise BudgetExceeded(f"run budget of ${settings.budget_usd_per_run:g} reached")
    if real:
        day = today()
        if day.get("blocked"):
            raise BudgetExceeded("Campaign accounting unavailable or unsettled; paid work blocked")
        if day["usd"] + worst > settings.budget_usd_per_day:
            raise BudgetExceeded(f"daily model budget of ${settings.budget_usd_per_day:g} reached")


def charge_usd(usd: float, real: bool, *, persist: bool = True) -> None:
    """real: a live, uncached call (counts toward today's spend)."""
    if led := LEDGER.get():
        led.usd += usd
    if real:
        if led := LEDGER.get():
            led.fresh_usd[ITEM.get()] = round(led.fresh_usd.get(ITEM.get(), 0.0) + usd, 9)
        if persist:
            _add_today(usd=usd)


def reserve_credits(n: float, real: bool) -> None:
    """Before a Tavily call: raise if n more credits would cross the item or the day cap."""
    led = LEDGER.get()
    if any(s["spent"] + n > s["cap"] for s in _CREDIT_SCOPES.get()):
        raise BudgetExceeded("Tavily credit cap for this step reached")
    spent = led.credits.get(ITEM.get(), 0.0) if led else 0.0
    if spent + n > settings.budget_tavily_credits_per_item:
        raise BudgetExceeded(f"Tavily cap of {settings.budget_tavily_credits_per_item:g} credits for this item reached")
    if real:
        day = today()
        if day.get("blocked"):
            raise BudgetExceeded("Campaign accounting unavailable or unsettled; paid work blocked")
        if day["credits"] + n > settings.budget_tavily_credits_per_day:
            raise BudgetExceeded(f"Tavily cap of {settings.budget_tavily_credits_per_day:g} credits for today reached")


def charge_credits(n: float, real: bool, *, persist: bool = True) -> None:
    for scope in _CREDIT_SCOPES.get():
        scope["spent"] += n
    if led := LEDGER.get():
        item = ITEM.get()
        led.credits[item] = led.credits.get(item, 0.0) + n
    if real:
        if led := LEDGER.get():
            led.fresh_credits[ITEM.get()] = led.fresh_credits.get(ITEM.get(), 0.0) + n
        if persist:
            _add_today(credits=n)


def usd_nano(value: float) -> int:
    if not math.isfinite(value) or value < 0:
        raise BudgetExceeded("Invalid model budget amount")
    return int((Decimal(str(value)) * 1_000_000_000).to_integral_value(rounding=ROUND_CEILING))


def reserve_payment(*, usd: float = 0, credits: int = 0) -> str:
    from . import campaign
    led = LEDGER.get()
    return campaign.reserve(settings.campaign_budget_file, campaign.Amount(usd_nano=usd_nano(usd), credits=credits),
        run=led.run_id if led else "", item=ITEM.get(), run_usd_nano=usd_nano(settings.budget_usd_per_run),
        day_usd_nano=usd_nano(settings.budget_usd_per_day), item_credits=math.floor(settings.budget_tavily_credits_per_item),
        day_credits=math.floor(settings.budget_tavily_credits_per_day), scopes=list(_CREDIT_SCOPES.get()))


def settle_payment(identifier: str, *, usd: float | None = None, credits: int | None = None) -> None:
    from . import campaign
    actual = campaign.Amount(usd_nano=usd_nano(usd or 0), credits=credits or 0) if usd is not None or credits is not None else None
    if actual is None:
        with campaign.transaction(settings.campaign_budget_file) as state:
            payment = state.payments[identifier]
            actual = payment.actual or payment.held
        usd, credits = actual.usd_nano / 1e9, actual.credits
        logging.getLogger("speccheck.budget").warning(
            "Provider usage unknown; settling reservation %s at worst case $%.9f / %s credits", identifier, usd, credits)
    led = LEDGER.get()
    known = led.accounted_payments.get(identifier) if led else None
    amount = (actual.usd_nano, actual.credits) if actual is not None else None
    if known is not None and amount is not None and known != amount:
        raise campaign.SettlementConflict("Conflicting campaign settlement")
    applied = True
    try:
        report, applied = campaign.settle(settings.campaign_budget_file, identifier, actual)
    except campaign.SettlementConflict:
        applied = False
        raise
    finally:
        # A failed persistence write cannot erase known paid usage from this item's attempt.
        if actual is not None and applied and led and identifier not in led.accounted_payments:
            led.accounted_payments[identifier] = amount
            if usd is not None:
                charge_usd(usd, real=True, persist=False)
            if credits is not None:
                charge_credits(credits, real=True, persist=False)
    if report["blocked"]:
        unknown_usage("Campaign accounting requires reconciliation; paid work is blocked")
    path = settings.cache_dir / "budget" / f"{report['day']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(report))
    temp.replace(path)


def recover_unknown_usage() -> None:
    """A single hosted process conservatively closes requests left by an earlier process."""
    from . import campaign
    with campaign.transaction(settings.campaign_budget_file) as state:
        abandoned = [identifier for identifier, p in state.payments.items()
                     if p.kind == "request" and p.actual is None and (p.unknown or p.owner != campaign.SESSION)]
    for identifier in abandoned:
        settle_payment(identifier)
