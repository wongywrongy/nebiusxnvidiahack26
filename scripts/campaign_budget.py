"""Initialize local campaign accounting once from explicitly selected historical day ledgers.

  python scripts/campaign_budget.py init --seed-day 2026-10-21 --seed-day 2026-10-22
  python scripts/campaign_budget.py status
  python scripts/campaign_budget.py init-judging --usd 75 --credits 6000
  python scripts/campaign_budget.py resolve-hold <id> --credits N --usd X

Never initializes during a provider call. Unknown or abandoned reservations require owner reconciliation.
"""

import argparse
from datetime import date
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.config import settings
from api.providers import budget, campaign


def initialize(days: list[str]) -> dict:
    seeds = {}
    if not days or len(set(days)) != len(days):
        raise ValueError("Select each historical campaign day exactly once")
    for day in days:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("Seed days must use YYYY-MM-DD")
        entry = json.loads((settings.cache_dir / "budget" / f"{day}.json").read_text())
        if entry.get("held_usd") or entry.get("held_credits") or entry.get("blocked") or "total_usd" in entry:
            raise ValueError("Seed requires reconciled historical ledgers, not another campaign report")
        credits = entry["credits"]
        if type(credits) not in (int, float) or not math.isfinite(credits) or credits != int(credits):
            raise ValueError("Historical credits must be whole, nonnegative numbers")
        seeds[day] = campaign.Amount(usd_nano=budget.usd_nano(entry["usd"]), credits=int(credits))
    campaign.initialize(settings.campaign_budget_file,
        campaign.Amount(usd_nano=sum(s.usd_nano for s in seeds.values()), credits=sum(s.credits for s in seeds.values())),
        seeds, campaign.Amount(usd_nano=20_000_000_000, credits=2000),
        campaign.Amount(usd_nano=10_000_000_000, credits=1000))
    return campaign.status(settings.campaign_budget_file)


def resolve_hold(identifier: str, *, credits: int, usd: float) -> dict:
    actual = campaign.Amount(usd_nano=budget.usd_nano(usd), credits=credits)
    path = settings.campaign_budget_file
    before = campaign.status(path)
    with campaign.transaction(path) as state:
        payment = state.payments.get(identifier)
        if payment is None or payment.actual is not None:
            raise budget.BudgetExceeded("No unresolved hold exists for this id")
        if payment.kind != "request":
            raise budget.BudgetExceeded("Only request holds can be resolved by this command")
    campaign.settle(path, identifier, actual)
    return {"id": identifier, "before": before, "after": campaign.status(path)}


def initialize_judging(*, usd: float, credits: int) -> dict:
    if usd <= 0 or credits <= 0:
        raise ValueError("Judging USD and credits must be positive")
    allowance = campaign.Amount(usd_nano=budget.usd_nano(usd), credits=credits)
    campaign.initialize(settings.campaign_budget_file, campaign.Amount(), {}, allowance, allowance)
    return campaign.status(settings.campaign_budget_file)


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "init-judging", "status", "install-controller", "resolve-hold"])
    parser.add_argument("id", nargs="?")
    parser.add_argument("--credits", type=int, help="actual credits confirmed by the owner in the provider dashboard")
    parser.add_argument("--usd", type=float, help="actual USD confirmed by the owner in the provider dashboard")
    parser.add_argument("--seed-day", action="append", default=[])
    parser.add_argument("--source", type=Path, help="existing campaign SQLite database for an explicit cold import")
    parser.add_argument("--controller-dir", type=Path, help="controller-only mounted POSIX filesystem")
    args = parser.parse_args()
    try:
        if args.action == "init-judging":
            if args.usd is None or args.credits is None:
                parser.error("init-judging requires --usd and --credits")
            print(json.dumps(initialize_judging(usd=args.usd, credits=args.credits), indent=2))
            return
        if args.action == "resolve-hold":
            if not args.id or args.credits is None or args.usd is None:
                parser.error("resolve-hold requires an id, --credits and --usd from the provider dashboard")
            print(json.dumps(resolve_hold(args.id, credits=args.credits, usd=args.usd), indent=2))
            return
        if args.action == "install-controller":
            if not args.source or not args.controller_dir:
                parser.error("install-controller requires --source and --controller-dir")
            from api.authority import install
            print(json.dumps(install(args.source, args.controller_dir), indent=2))
            sys.exit(0)
        print(json.dumps(initialize(args.seed_day) if args.action == "init" else
                         campaign.status(settings.campaign_budget_file), indent=2))
    except (ValueError, OSError, budget.BudgetExceeded) as error:
        sys.exit(str(error))


if __name__ == "__main__":
    cli()
