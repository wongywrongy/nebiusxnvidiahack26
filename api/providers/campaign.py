"""Local, single-writer campaign reservations. SQLite owns money; cache files are reports only."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .budget import BudgetExceeded

SESSION = uuid.uuid4().hex
FAILED_SETTLEMENTS: set[tuple[str, str]] = set()


class SettlementConflict(BudgetExceeded):
    pass


class Amount(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    usd_nano: int = Field(default=0, ge=0)
    credits: int = Field(default=0, ge=0)


class Payment(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    run: str = Field(min_length=1)
    item: str = Field(min_length=1)
    day: str
    phase: str
    owner: str
    held: Amount
    actual: Amount | None = None
    unknown: bool = False
    scopes: list[str] = []


class State(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    version: int = 1
    seed: Amount
    day_seed: dict[str, Amount]
    limit: Amount
    phases: dict[str, Amount]
    phase: str = "engineering"
    payments: dict[str, Payment] = {}
    blocked: bool = False


def _sum(amounts):
    amounts = list(amounts)
    return Amount(usd_nano=sum(a.usd_nano for a in amounts), credits=sum(a.credits for a in amounts))


def _charge(payment):
    return payment.actual or payment.held


def _validate(state):
    if state.version != 1 or state.phase not in state.phases or _sum(list(state.day_seed.values())) != state.seed:
        raise ValueError("Inconsistent campaign seed")
    allocated = _sum([state.seed, *state.phases.values()])
    if allocated.usd_nano > state.limit.usd_nano or allocated.credits > state.limit.credits:
        raise ValueError("Campaign allocation exceeds its ceiling")
    for p in state.payments.values():
        if p.phase not in state.phases or datetime.fromisoformat(p.day).date().isoformat() != p.day:
            raise ValueError("Invalid payment provenance")
    for day in state.day_seed:
        if datetime.fromisoformat(day).date().isoformat() != day:
            raise ValueError("Invalid seed date")


def initialize(path: Path, seed: Amount, day_seed: dict[str, Amount], limit: Amount, engineering: Amount):
    remaining = Amount(usd_nano=limit.usd_nano - seed.usd_nano - engineering.usd_nano,
                       credits=limit.credits - seed.credits - engineering.credits)
    state = State(seed=seed, day_seed=day_seed, limit=limit, phases={"engineering": engineering, "final": remaining})
    _validate(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("CREATE TABLE campaign (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
        conn.execute("INSERT INTO campaign VALUES (1, ?)", (state.model_dump_json(),))


@contextmanager
def transaction(path: Path):
    conn = None
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None)
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT data FROM campaign WHERE id=1").fetchone()
        state = State.model_validate_json(row[0])
        _validate(state)
        yield state
        state = State.model_validate(state.model_dump())
        _validate(state)
        conn.execute("UPDATE campaign SET data=? WHERE id=1", (state.model_dump_json(),))
        conn.execute("COMMIT")
    except BudgetExceeded:
        raise
    except Exception as error:
        raise BudgetExceeded("Campaign accounting unavailable; no paid request allowed") from error
    finally:
        if conn:
            conn.close()


def reserve(path: Path, held: Amount, *, run: str, item: str, run_usd_nano: int, day_usd_nano: int,
            item_credits: int, day_credits: int, scopes: list[dict]) -> str:
    if not run or not item or min(run_usd_nano, day_usd_nano, item_credits, day_credits) < 0:
        raise BudgetExceeded("Paid requests require valid run, item and cap context")
    if any(p == str(path.resolve()) for p, _ in FAILED_SETTLEMENTS):
        raise BudgetExceeded("Failed campaign settlement requires reconciliation")
    with transaction(path) as state:
        if state.blocked or any(p.unknown or p.actual is None and p.owner != SESSION for p in state.payments.values()):
            raise BudgetExceeded("Unsettled campaign usage requires reconciliation before paid work")
        day = datetime.now(timezone.utc).date().isoformat()
        payments = list(state.payments.values())
        limits = [
            (_sum([state.seed, *map(_charge, payments)]), state.limit),
            (_sum([_charge(p) for p in payments if p.phase == state.phase]), state.phases[state.phase]),
            (_sum([state.day_seed.get(day, Amount()), *[_charge(p) for p in payments if p.day == day or p.actual is None]]),
             Amount(usd_nano=day_usd_nano, credits=day_credits)),
            (_sum([_charge(p) for p in payments if p.run == run]), Amount(usd_nano=run_usd_nano, credits=state.limit.credits)),
            (_sum([_charge(p) for p in payments if p.run == run and p.item == item]),
             Amount(usd_nano=state.limit.usd_nano, credits=item_credits)),
        ]
        if any(spent.usd_nano + held.usd_nano > cap.usd_nano or spent.credits + held.credits > cap.credits for spent, cap in limits):
            raise BudgetExceeded("Campaign, allocation, day, run or item cap would be exceeded")
        for scope in scopes:
            pending = sum(p.held.credits for p in payments if p.actual is None and scope["id"] in p.scopes)
            if scope["spent"] + pending + held.credits > scope["cap"]:
                raise BudgetExceeded("Tavily step cap would be exceeded including pending calls")
        identifier = uuid.uuid4().hex
        state.payments[identifier] = Payment(run=run, item=item, day=day, phase=state.phase, owner=SESSION,
                                             held=held, scopes=[s["id"] for s in scopes])
        return identifier


def settle(path: Path, identifier: str, actual: Amount | None) -> tuple[dict, bool]:
    key = (str(path.resolve()), identifier)
    try:
        with transaction(path) as state:
            payment = state.payments[identifier]
            applied = payment.actual is None and actual is not None
            if payment.actual is not None:
                if payment.actual != actual:
                    raise SettlementConflict("Conflicting campaign settlement")
            elif actual is None:
                payment.unknown = True
            else:
                payment.actual = actual
                payment.unknown = False
                if actual.usd_nano > payment.held.usd_nano or actual.credits > payment.held.credits:
                    state.blocked = True
            result = report(state, payment.day)
        FAILED_SETTLEMENTS.discard(key)
        return result, applied
    except SettlementConflict:
        raise
    except Exception:
        FAILED_SETTLEMENTS.add(key)
        raise


def report(state: State, day: str) -> dict:
    payments = list(state.payments.values())
    actual = _sum([state.day_seed.get(day, Amount()), *[p.actual for p in payments if p.day == day and p.actual is not None]])
    held = _sum([p.held for p in payments if p.actual is None])
    total = _sum([state.seed, *[_charge(p) for p in payments]])
    phase = _sum([_charge(p) for p in payments if p.phase == state.phase])
    return {"day": day, "usd": actual.usd_nano / 1e9, "credits": actual.credits,
            "held_usd": held.usd_nano / 1e9, "held_credits": held.credits,
            "total_usd": total.usd_nano / 1e9, "total_credits": total.credits,
            "phase": state.phase, "phase_usd": phase.usd_nano / 1e9, "phase_credits": phase.credits,
            "usd_limit": state.limit.usd_nano / 1e9, "credit_limit": state.limit.credits,
            "phase_usd_limit": state.phases[state.phase].usd_nano / 1e9, "phase_credit_limit": state.phases[state.phase].credits,
            "blocked": state.blocked or any(p.unknown or p.actual is None and p.owner != SESSION for p in payments)}


def status(path: Path) -> dict:
    with transaction(path) as state:
        result = report(state, datetime.now(timezone.utc).date().isoformat())
        result["blocked"] |= any(p == str(path.resolve()) for p, _ in FAILED_SETTLEMENTS)
        return result
