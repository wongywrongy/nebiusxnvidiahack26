"""Per-arm table for the accuracy A/B: python runs/arms/compare.py A B C [D]"""
import glob, json, statistics, sys
from pathlib import Path

HERE = Path(__file__).parent
REC = HERE.parent.parent.parent / "customer-feedback-finish" / "runs" / "recorded"
REFS = {"A0": REC / "20261028-171142-5ca0fc", "Oct22": REC / "20261022-181611-a9d0b5"}


def load(run: Path, scores: Path | None = None):
    s = json.loads((scores or run / "scores.json").read_text())
    res = {Path(f).stem: json.loads(Path(f).read_text()) for f in glob.glob(str(run / "results" / "*.json"))}
    return s, res


def load_arm(arm):
    scores = HERE / arm / "scores.json"
    return load(HERE / arm / json.loads(scores.read_text())["run_id"], scores)


def decisions(res):
    return {cid: r["decision"] for cid, r in sorted(res.items())}


def report(arm, refs):
    s, res = load_arm(arm)
    rows = s["rows"]
    times = sorted(r["time_ms"] / 1000 for r in rows)
    q = s["quote_gate"]
    trunc = sum(1 for r in res.values() for u in r["usage"] if u.get("finish_reason") == "length")
    trunc += sum(1 for r in res.values() for w in r.get("warnings", []) + r.get("diagnostics", []) if "MAX_OUTPUT_TOKENS" in json.dumps(w) or "cut off at the token limit" in json.dumps(w))
    reason_tok = sum(u.get("reasoning_tokens") or 0 for r in res.values() for u in r["usage"])
    p90 = times[min(len(times) - 1, round(0.9 * (len(times) - 1)))]
    print(f"\n### Arm {arm}  run {s['run_id']}")
    print("| Measure | Value |\n| --- | --- |")
    for k in ("right_call", "caught", "false_alarms", "fixes_passing"):
        print(f"| {k.replace('_', ' ')} | {s[k]['n']}/{s[k]['of']} |")
    print(f"| unnecessary notes | {s['unnecessary_notes']['n']} |")
    print(f"| invalid items | {s['validity']['invalid_items']}/{s['validity']['requested_items']} |")
    print(f"| MAX_OUTPUT_TOKENS hits | {trunc} |")
    print(f"| claims kept/extracted | {q['claims_kept']}/{q['claims_extracted']} ({q['claims_kept'] / max(1, q['claims_extracted']):.1%}) |")
    print(f"| web values kept/read | {q['web_values_kept']}/{q['web_values_read']} ({q['web_values_kept'] / max(1, q['web_values_read']):.1%}) |")
    top = list(q.get("drop_reasons", {}).items())[:5]
    print(f"| top 5 drop reasons | {'; '.join(f'{k} {v}' for k, v in top) or 'n/a'} |")
    full = sum(r["cost_usd"] for r in rows) / len(rows)
    print(f"| cost per item, 8 cases, model+web priced as if uncached | ${full:.4f} |")
    print(f"| cost per item, all 10, model priced as if uncached | ${sum(sum(u['cost_usd'] for u in r['usage']) for r in res.values()) / len(res):.4f} |")
    print(f"| run fresh spend | ${s['run_fresh_spend']['usd']:.4f} / {s['run_fresh_spend']['credits']:g} credits |")
    print(f"| p50 / p90 item time | {statistics.median(times):.1f} s / {p90:.1f} s |")
    print(f"| reasoning tokens | {reason_tok} |")
    mine = decisions(res)
    for name, (_, rres) in refs.items():
        other = decisions(rres)
        diff = [f"{c}: {other.get(c)} -> {d}" for c, d in mine.items() if c in other and other[c] != d]
        print(f"| changed vs {name} | {'; '.join(diff) or 'none'} |")
    print(f"| decisions | {', '.join(f'{c} {d}' for c, d in mine.items())} |")
    return s


if __name__ == "__main__":
    refs = {k: load(v) for k, v in REFS.items()}
    for arm in sys.argv[1:]:
        report(arm, refs)
