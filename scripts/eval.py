"""Scoreboard: run the test cases and compare against the answer key in data/cases/cases.json.

  python scripts/eval.py                 # all cases, mock mode by default
  python scripts/eval.py --case c03      # one case
  python scripts/eval.py --samples       # the sample inbox (data/cases/samples.json); in mock mode, only recorded ones
  SPECCHECK_MODE=live python scripts/eval.py --case c03

Prints per-case results and the panel numbers: right call, problems caught, false alarms on clean
items, fixes that pass, time and cost per submittal. A full run (all cases) also writes
runs/scores.json, which GET /api/scores and the Results page show.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import PRICES, settings  # noqa: E402
from api.pipeline.cases import all_cases, all_samples, mock_ready  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402
from api.pipeline.scores import scores  # noqa: E402

async def main(case_ids: list[str]) -> int:
    run = Run(case_ids, delay_ms=0)
    await execute(run)
    s = scores(run, case_ids)

    print(f"\nmode={settings.mode}  run={run.id}\n")
    zero = sorted({m for m in settings.models.values() if m and not all(PRICES.get(m, (0, 0)))})
    if settings.live and zero:
        print(f"WARNING: no price for {', '.join(zero)} in api/config.py PRICES: reported model cost is too low.\n")
    print(f"{'case':<5} {'expected':<18} {'got':<18} {'problems expected':<22} {'found':<26} {'fix':<5} {'ms':>6} {'cost $':>8} {'credits':>7}")
    for r in s["rows"]:
        if r.get("error"):
            print(f"{r['id']:<5} ERROR  (see runs/{run.id}/events.jsonl)")
            continue
        fix = "-" if r["fix"] is None else ("pass" if r["fix"]["passes"] else "none")
        mark = "✓" if r["right_call"] and r["caught"] == len(r["expected_problems"]) else "✗"
        print(f"{r['id']:<5} {r['expected']:<18} {r['decision']:<18} {','.join(r['expected_problems']) or '-':<22} "
              f"{','.join(r['found_problems']) or '-':<26} {fix:<5} {r['time_ms']:>6} {r['cost_usd']:>8.4f} {r['web_credits']:>7.0f} {mark}")

    rc, ca, fa, fx = s["right_call"], s["caught"], s["false_alarms"], s["fixes_passing"]
    print("\nAnswer-key panel")
    print(f"  right call                      {rc['n']} of {rc['of']}")
    print(f"  planted problems caught         {ca['n']} of {ca['of']}")
    print(f"  clean packages wrongly flagged  {fa['n']} of {fa['of']}")
    print(f"  fixes that pass the spec        {fx['n']} of {fx['of']}")
    print(f"  average time per submittal      {s['time_ms_per_item'] / 1000:.1f} s")
    print(f"  cost per submittal (model+web)  ${s['cost_usd_per_item']:.4f}" + ("   (mock: estimated token counts)" if not settings.live else ""))

    if sorted(case_ids) == sorted(all_cases()):
        settings.scores_file.parent.mkdir(parents=True, exist_ok=True)
        settings.scores_file.write_text(json.dumps(s, indent=2))
        print(f"\nwrote {settings.scores_file.relative_to(ROOT)}")
    # Fails on: a wrong call, a missed problem, a false alarm, or a fix marked "Passes" with any check not passed.
    bad_fix = [c for r in run.results.values() for f in r.findings if f.fix for c in f.fix.candidates
               if c.passes and not all(k.ok is True for k in c.checks)]
    return 0 if rc["n"] == rc["of"] and ca["n"] == ca["of"] and fa["n"] == 0 and not bad_fix else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case", action="append", help="case id, repeatable (default: all)")
    p.add_argument("--samples", action="store_true", help="score the sample inbox instead of the test cases")
    args = p.parse_args()
    if args.samples:
        ids = sorted(i for i, s in all_samples().items() if settings.live or mock_ready(s))
    else:
        ids = args.case or sorted(all_cases())
    sys.exit(asyncio.run(main(ids)))
