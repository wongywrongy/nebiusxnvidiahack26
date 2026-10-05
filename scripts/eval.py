"""Scoreboard: run the test cases and compare against the answer key in data/cases/cases.json.

  python scripts/eval.py                 # all cases, mock mode by default
  python scripts/eval.py --case c03      # one case
  SPECCHECK_MODE=live python scripts/eval.py --case c03

Prints per-case results and the four numbers for the demo panel:
problems caught, clean packages wrongly flagged, average time, cost per submittal.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.pipeline.cases import all_cases  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402

FLAG = {"fail", "outdated"}


def found_problems(result) -> set[str]:
    out = set()
    for f in result.findings:
        if f.verdict in FLAG:
            out.add(f.check)
        if f.verdict == "note" and f.check == "currency":
            out.add("currency_note")
    return out


async def main(case_ids: list[str]) -> int:
    run = Run(case_ids, delay_ms=0)
    await execute(run)
    cases = all_cases()

    planted = caught = clean = false_flags = decision_ok = 0
    print(f"\nmode={settings.mode}  run={run.id}\n")
    zero = [t for t, (pin, pout) in settings.prices.items() if not pin or not pout]
    if settings.live and zero:
        print(f"WARNING: price is 0 for {', '.join(zero)} in api/config.py: reported model cost is too low.\n")
    print(f"{'case':<5} {'expected':<18} {'got':<18} {'problems expected':<22} {'found':<26} {'ms':>6} {'cost $':>8} {'credits':>7}")
    for cid in case_ids:
        exp = cases[cid]["expected"]
        res = run.results.get(cid)
        if res is None:
            print(f"{cid:<5} ERROR  (see runs/{run.id}/events.jsonl)")
            continue
        want = set(exp["problems"])
        got = found_problems(res)
        planted += len(want)
        caught += len(want & got)
        if not want:
            clean += 1
            if got & {"spec", "currency", "validity", "status", "completeness"}:
                false_flags += 1
        ok = res.decision == exp["decision"]
        decision_ok += ok
        mark = "✓" if ok and want <= got else "✗"
        print(f"{cid:<5} {exp['decision']:<18} {res.decision:<18} {','.join(sorted(want)) or '-':<22} "
              f"{','.join(sorted(got)) or '-':<26} {res.duration_ms:>6} {res.cost_usd:>8.4f} {res.web_credits:>7.0f} {mark}")

    results = list(run.results.values())
    n = max(len(results), 1)
    avg_ms = sum(r.duration_ms for r in results) / n
    avg_cost = sum(r.cost_usd + r.web_credits * settings.tavily_credit_usd for r in results) / n
    print("\nAnswer-key panel")
    print(f"  planted problems caught         {caught} of {planted}")
    print(f"  clean packages wrongly flagged  {false_flags} of {clean}")
    print(f"  decisions matching the key      {decision_ok} of {len(case_ids)}")
    print(f"  average time per submittal      {avg_ms / 1000:.1f} s")
    print(f"  cost per submittal (model+web)  ${avg_cost:.4f}" + ("   (mock: model prices are placeholders)" if not settings.live else ""))
    return 0 if decision_ok == len(case_ids) and caught == planted and false_flags == 0 else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case", action="append", help="case id, repeatable (default: all)")
    args = p.parse_args()
    ids = args.case or sorted(all_cases())
    sys.exit(asyncio.run(main(ids)))
