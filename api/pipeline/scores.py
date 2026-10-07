"""Answer-key scores: shared by scripts/eval.py and the Results page's "Run the scoring set"."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from .cases import all_cases
from .decide import FLAGGED



def found_problems(result) -> set[str]:
    out = set()
    for f in result.findings:
        if f.verdict in FLAGGED:
            out.add(f.check)
        if f.verdict == "note" and f.check == "currency":
            out.add("currency_note")
    return out


def best_fix(result):
    """(fix, best candidate) of the first finding with a fix; candidate None when nothing passes."""
    fix = next((f.fix for f in result.findings if f.fix), None)
    return fix, next((c for c in fix.candidates if c.passes), None) if fix else None


def item_cost(result) -> float:
    return result.cost_usd + result.web_credits * settings.tavily_credit_usd


def scores(run, case_ids: list[str]) -> dict:
    cases = all_cases()
    rows = []
    for cid in case_ids:
        exp, res = cases[cid]["expected"], run.results.get(cid)
        want = set(exp["problems"])
        row = {"id": cid, "title": cases[cid]["title"], "product": cases[cid].get("product", ""),
               "expected": exp["decision"], "expected_problems": sorted(want)}
        if res is None:
            rows.append({**row, "error": True})
            continue
        got = found_problems(res)
        fix, cand = best_fix(res)
        rows.append({
            **row, "decision": res.decision, "found_problems": sorted(got), "right_call": res.decision == exp["decision"],
            "caught": len(want & got), "false_alarm": not want and bool(got & {"spec", "currency", "validity", "status", "completeness"}),
            "fix": None if exp["decision"] != "send_back" else {
                "suggest": cand.name if cand else None, "passes": cand is not None,
                "candidates": len(fix.candidates) if fix else 0},
            "time_ms": res.duration_ms, "model_cost_usd": round(res.cost_usd, 6), "web_credits": res.web_credits,
            "cost_usd": round(item_cost(res), 6),
        })
    ok = [r for r in rows if not r.get("error")]
    n = max(len(ok), 1)
    fixes = [r["fix"] for r in ok if r.get("fix")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": settings.mode, "run_id": run.id, "models": settings.models,
        "right_call": {"n": sum(r["right_call"] for r in ok), "of": len(case_ids)},
        "caught": {"n": sum(r["caught"] for r in ok), "of": sum(len(cases[c]["expected"]["problems"]) for c in case_ids)},
        "false_alarms": {"n": sum(r["false_alarm"] for r in ok),
                         "of": sum(not cases[c]["expected"]["problems"] for c in case_ids)},
        "fixes_passing": {"n": sum(f["passes"] for f in fixes), "of": sum(cases[c]["expected"]["decision"] == "send_back" for c in case_ids)},
        "time_ms_per_item": round(sum(r["time_ms"] for r in ok) / n),
        "cost_usd_per_item": round(sum(r["cost_usd"] for r in ok) / n, 6),
        "rows": rows,
    }


async def run_scoring_set() -> dict:
    """Run every case, score it against the key, and write runs/scores.json."""
    import json

    from .runner import Run, execute

    ids = sorted(all_cases())
    run = await execute(Run(ids, delay_ms=0))
    s = scores(run, ids)
    settings.scores_file.parent.mkdir(parents=True, exist_ok=True)
    settings.scores_file.write_text(json.dumps(s, indent=2))
    return s
