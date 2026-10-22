"""Answer-key scores: shared by scripts/eval.py and the Results page's "Run the scoring set"."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from ..readiness import invalid_reasons, release_checks
from .cases import all_cases, all_samples
from .decide import FLAGGED
from .metrics import FIELDS



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
    return fix, next((c for c in fix.candidates if c.passes and c.checks and all(k.ok is True for k in c.checks)), None) if fix else None


def item_cost(result) -> float:
    return result.cost_usd + result.web_credits * settings.tavily_credit_usd


def scores(run, case_ids: list[str]) -> dict:
    cases = {**all_cases(), **all_samples()}  # samples score against their own expected (scripts/eval.py --samples)
    rows = []
    for cid in case_ids:
        exp, res = cases[cid]["expected"], run.results.get(cid)
        want = set(exp["problems"])
        row = {"id": cid, "title": cases[cid]["title"], "product": cases[cid].get("product", ""),
               "expected": exp["decision"], "expected_problems": sorted(want)}
        attempt = getattr(run, "attempts", {}).get(cid, {})
        problems = list(attempt.get("diagnostics", []))
        if res:
            problems += [d for d in invalid_reasons(res) if d not in problems]
        row.update(valid=res is not None and not problems, diagnostics=problems,
                   warnings=res.warnings if res else [], queue_ms=attempt.get("queue_ms", res.queue_ms if res else 0),
                   fresh_model_cost_usd=attempt.get("fresh_model_cost_usd", res.fresh_model_cost_usd if res else 0),
                   fresh_web_credits=attempt.get("fresh_web_credits", res.fresh_web_credits if res else 0))
        if res is None:
            fresh = row["fresh_model_cost_usd"]
            rows.append({**row, "error": True, "valid": False, "time_ms": attempt.get("duration_ms", 0),
                         "model_cost_usd": fresh, "web_credits": row["fresh_web_credits"],
                         "cost_usd": fresh + row["fresh_web_credits"] * settings.tavily_credit_usd})
            continue
        got = found_problems(res)
        fix, cand = best_fix(res)
        rows.append({
            **row, "decision": res.decision, "found_problems": sorted(got), "right_call": res.decision == exp["decision"],
            "caught": len(want & got), "false_alarm": not want and bool(got & {"spec", "currency", "validity", "status", "completeness"}),
            "unnecessary_note": exp["decision"] == "approve" and res.decision == "approve_with_note",
            "fix": None if exp["decision"] != "send_back" else {
                "suggest": cand.name if cand else None, "passes": cand is not None,
                "candidates": len(fix.candidates) if fix else 0},
            "time_ms": res.duration_ms, "model_cost_usd": round(res.cost_usd, 6), "web_credits": res.web_credits,
            "cost_usd": round(item_cost(res), 6),
            **{key: getattr(res, key) for key in FIELDS},
        })
    ok = [r for r in rows if not r.get("error")]
    n = max(len(case_ids), 1)
    fixes = [r["fix"] for r in ok if r.get("fix")]
    gates = {key: sum(r[key] for r in ok) for key in FIELDS}
    investigations = [inv for cid in case_ids if (res := run.results.get(cid)) for inv in res.investigations]
    primary = [inv for inv in investigations if inv.purpose == "primary"]
    for prefix, read in (("claims", "claims_extracted"), ("web_values", "web_values_read")):
        gates[f"{prefix}_drop_rate"] = (1 - gates[f"{prefix}_kept"] / gates[read]) if gates[read] else None
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": settings.mode, "run_id": run.id, "models": settings.models,
        "quote_gate": gates,
        "tuning": {key: getattr(settings, key) for key in (
            "thinking", "thinking_tasks", "max_output_tokens", "max_page_chars", "web_source_chars", "search_depth", "extract_depth",
            "search_max_results", "investigate_credit_cap", "investigate_max_steps", "map_limit")},
        "right_call": {"n": sum(r["right_call"] for r in ok), "of": len(case_ids)},
        "caught": {"n": sum(r["caught"] for r in ok), "of": sum(len(cases[c]["expected"]["problems"]) for c in case_ids)},
        "false_alarms": {"n": sum(r["false_alarm"] for r in ok),
                         "of": sum(not cases[c]["expected"]["problems"] for c in case_ids)},
        "fixes_passing": {"n": sum(f["passes"] for f in fixes), "of": sum(cases[c]["expected"]["decision"] == "send_back" for c in case_ids)},
        "unnecessary_notes": {"n": sum(r.get("unnecessary_note", False) for r in rows),
                              "of": sum(cases[c]["expected"]["decision"] == "approve" for c in case_ids)},
        "validity": {"invalid_items": sum(not r["valid"] for r in rows), "requested_items": len(case_ids)},
        "fresh_model_cost_usd": round(sum(r["fresh_model_cost_usd"] for r in rows), 6),
        "fresh_web_credits": sum(r["fresh_web_credits"] for r in rows),
        "run_fresh_spend": {"usd": round(sum(run.ledger.fresh_usd.values()), 6),
                            "credits": sum(run.ledger.fresh_credits.values())},
        "investigations": {"scripted_unconfirmed_items": sum(
            any(i.purpose == "primary" for i in res.investigations) or any(f.check == "currency" and f.verdict == "unverified" for f in res.findings)
            for cid in case_ids if (res := run.results.get(cid))),
            "primary_runs": len(primary), "resolved": sum(i.resolution in ("problem_found", "values_confirmed") for i in primary),
            "revision_only": sum(i.resolution == "revision_only" for i in primary),
            "capped": sum(i.outcome == "capped" for i in primary),
            "replacement_runs": sum(i.purpose == "replacement" for i in investigations),
            "replacement_capped": sum(i.outcome == "capped" and i.purpose == "replacement" for i in investigations)},
        "manifest": getattr(run, "manifest", None),
        "time_ms_per_item": round(sum(r["time_ms"] for r in rows) / n),
        "cost_usd_per_item": round(sum(r["cost_usd"] for r in rows) / n, 6),
        "rows": rows,
    }
    result["release_gate"] = {"passed": not (issues := release_checks(result)), "issues": issues}
    return result


async def run_scoring_set(*, mock: bool = False) -> dict:
    """Run every case, score it against the key, and write runs/scores.json."""
    import json

    from .runner import Run, execute

    ids = sorted(all_cases())
    run = await execute(Run(ids, delay_ms=0, mock=ids if mock else []))
    s = scores(run, ids)
    if mock:
        s["mode"] = "mock"
    settings.scores_file.parent.mkdir(parents=True, exist_ok=True)
    settings.scores_file.write_text(json.dumps(s, indent=2))
    return s
