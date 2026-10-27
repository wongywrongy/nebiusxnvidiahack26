"""Scoreboard: run the test cases and compare against the answer key in data/cases/cases.json.

  python scripts/eval.py                 # all cases, mock mode by default
  python scripts/eval.py --case c03      # one case
  python scripts/eval.py --samples       # the sample inbox (data/cases/samples.json); in mock mode, only recorded ones
  python scripts/eval.py --blind-set path/to/frozen-set --check  # validate reviewed sources without providers
  SPECCHECK_MODE=live python scripts/eval.py --case c03

Prints per-case results and the panel numbers: right call, problems caught, false alarms on clean
items, fixes that pass, time and cost per submittal. A full run (all cases) also writes
runs/scores.json, which GET /api/scores and the Results page show.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import PRICES, settings  # noqa: E402
from api.pipeline.cases import all_cases, all_samples, mock_ready  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402
from api.pipeline.scores import scores  # noqa: E402

async def main(case_ids: list[str], out: Path | None = None, *, extra_ids: list[str] | None = None,
               release_gate: bool = False, catalog: dict | None = None,
               validation_set_sha256: str | None = None) -> int:
    inputs = None if catalog is None else {key: {k: v for k, v in row.items() if k != "expected"}
                                           for key, row in catalog.items()}
    run = Run(list(dict.fromkeys([*case_ids, *(extra_ids or [])])), delay_ms=0, catalog=inputs)
    if validation_set_sha256:
        run.manifest["validation_set_sha256"] = validation_set_sha256
        (run.dir / "manifest.json").write_text(json.dumps(run.manifest, indent=2))
    await execute(run)
    s = scores(run, case_ids, catalog=catalog)
    s.update(runner=os.environ.get("RECHECK_RUNNER", "local"), job_name=os.environ.get("JOB_NAME"))
    (run.dir / "scores.json").write_text(json.dumps(s, indent=2))

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
    print(f"  invalid acceptance items        {s['validity']['invalid_items']} of {len(case_ids)}")
    print(f"  unnecessary notes               {s['unnecessary_notes']['n']}")
    print(f"  fresh model spend / web credits ${s['run_fresh_spend']['usd']:.6f} / {s['run_fresh_spend']['credits']:g}")
    print(f"  case evidence gate              {'passed' if s['release_gate']['passed'] else '; '.join(s['release_gate']['issues'])}")
    for row in s["rows"]:
        if not row["valid"]:
            print(f"  INVALID {row['id']}: " + "; ".join(d["message"] for d in row["diagnostics"]))
    print(f"  average time per submittal      {s['time_ms_per_item'] / 1000:.1f} s")
    print(f"  cost per submittal (model+web)  ${s['cost_usd_per_item']:.4f}" + ("   (mock: estimated token counts)" if not settings.live else ""))
    gate = s["quote_gate"]
    def rate(key):
        return "n/a" if gate[key] is None else f"{gate[key]:.1%}"
    print(f"Quote gate: claims {gate['claims_kept']}/{gate['claims_extracted']} kept ({rate('claims_drop_rate')} dropped); "
          f"web values {gate['web_values_kept']}/{gate['web_values_read']} kept ({rate('web_values_drop_rate')} dropped)")

    if out is not None or catalog is None and sorted(case_ids) == sorted(all_cases()):
        path = out or settings.scores_file
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(s, indent=2))
        temp.replace(path)
        print(f"\nwrote {path}")
    # Fails on: a wrong call, a missed problem, a false alarm, or a fix marked "Passes" with any check not passed.
    bad_fix = [c for r in run.results.values() for f in r.findings if f.fix for c in f.fix.candidates
               if c.passes and (not c.checks or not all(k.ok is True for k in c.checks))]
    if s["validity"]["invalid_items"]:
        return 2
    if release_gate and not s["release_gate"]["passed"]:
        return 1
    return 0 if rc["n"] == rc["of"] and ca["n"] == ca["of"] and fa["n"] == 0 and not bad_fix else 1


def cli() -> int:
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group()
    group.add_argument("--case", action="append", help="case id, repeatable (default: all)")
    group.add_argument("--samples", action="store_true", help="score the sample inbox instead of the test cases")
    group.add_argument("--blind-set", type=Path, help="six frozen, owner-reviewed packages; live mode required")
    p.add_argument("--check", action="store_true", help="check --blind-set sources/review without running providers")
    p.add_argument("--release-gate", action="store_true", help="require case evidence prerequisites; full promotion uses scripts/check_release.py")
    p.add_argument("--out", "--write", type=Path, help="scoreboard output path (default: runs/scores.json for all cases)")
    args = p.parse_args()
    if args.check and not args.blind_set:
        p.error("--check requires --blind-set")
    if args.blind_set and args.release_gate:
        p.error("--release-gate checks cases only; use scripts/check_release.py for complete release promotion")
    if args.blind_set:
        from api.release import _blind
        try:
            catalog, _, digest = _blind(args.blind_set)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, IndexError):
            p.error("Blind set is missing, invalid or not owner-reviewed; no run started")
        if args.check:
            print(json.dumps({"packages": len(catalog), "validation_set_sha256": digest, "checked_only": True}))
            return 0
        if not settings.live:
            p.error("Blind evaluation requires SPECCHECK_MODE=live; no fixture fallback is allowed")
        return asyncio.run(main(sorted(catalog), args.out, catalog=catalog, validation_set_sha256=digest))
    if args.samples:
        ids = sorted(i for i, s in all_samples().items() if settings.live or mock_ready(s))
    else:
        ids = args.case or sorted(all_cases())
    return asyncio.run(main(ids, args.out, release_gate=args.release_gate))


if __name__ == "__main__":
    sys.exit(cli())
