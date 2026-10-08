"""Spend ledger: USD per run and per day, Tavily credits per item and per day.

The runner opens a Ledger per run (LEDGER) and names the item it is working on (ITEM); both are
context variables, so concurrent items each see their own. Providers check before a call and
charge after it. A cap raises BudgetExceeded; the runner turns that into a "couldn't confirm" step.
Today's totals (live, uncached calls only) are kept in .cache/budget/<date>.json for /api/health.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from ..config import settings


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self) -> None:
        self.usd = 0.0
        self.credits: dict[str, float] = {}  # item id -> Tavily credits


LEDGER: ContextVar[Optional[Ledger]] = ContextVar("ledger", default=None)
ITEM: ContextVar[str] = ContextVar("item", default="")


def _day_file():
    return settings.cache_dir / "budget" / f"{datetime.now(timezone.utc).date()}.json"


def today() -> dict:
    p = _day_file()
    return json.loads(p.read_text()) if p.exists() else {"usd": 0.0, "credits": 0.0}


def _add_today(usd: float = 0.0, credits: float = 0.0) -> None:
    # ponytail: read-modify-write with no lock, fine for one worker; use a DB row if we run several.
    t = today()
    t = {"usd": round(t["usd"] + usd, 6), "credits": t["credits"] + credits}
    p = _day_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(t))


def check_usd(worst: float = 0.0, real: bool = False) -> None:
    """Before a model call: raise if its worst-case cost would cross the run cap, or (real) today's cap."""
    led = LEDGER.get()
    if led and (led.usd >= settings.budget_usd_per_run or led.usd + worst > settings.budget_usd_per_run):
        raise BudgetExceeded(f"run budget of ${settings.budget_usd_per_run:g} reached")
    if real and today()["usd"] + worst > settings.budget_usd_per_day:
        raise BudgetExceeded(f"daily model budget of ${settings.budget_usd_per_day:g} reached")


def charge_usd(usd: float, real: bool) -> None:
    """real: a live, uncached call (counts toward today's spend)."""
    if led := LEDGER.get():
        led.usd += usd
    if real:
        _add_today(usd=usd)


def reserve_credits(n: float, real: bool) -> None:
    """Before a Tavily call: raise if n more credits would cross the item or the day cap."""
    led = LEDGER.get()
    spent = led.credits.get(ITEM.get(), 0.0) if led else 0.0
    if spent + n > settings.budget_tavily_credits_per_item:
        raise BudgetExceeded(f"Tavily cap of {settings.budget_tavily_credits_per_item:g} credits for this item reached")
    if real and today()["credits"] + n > settings.budget_tavily_credits_per_day:
        raise BudgetExceeded(f"Tavily cap of {settings.budget_tavily_credits_per_day:g} credits for today reached")


def charge_credits(n: float, real: bool) -> None:
    if led := LEDGER.get():
        item = ITEM.get()
        led.credits[item] = led.credits.get(item, 0.0) + n
    if real:
        _add_today(credits=n)
