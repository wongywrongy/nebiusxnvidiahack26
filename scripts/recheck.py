"""The nightly re-check: approved submittals, checked again against the manufacturer's documents on the live web.

  python scripts/recheck.py                          # every watched item (cases.json "watch"), live
  python scripts/recheck.py --ids c01 c07            # these items
  python scripts/recheck.py --post https://speccheck.example.com   # also report to the running app (ADMIN_TOKEN)
  SPECCHECK_MODE=mock python scripts/recheck.py      # dry run from fixtures, no API calls

An approved submittal is the record of what gets installed. This job runs the same pipeline a new submittal gets
(Nemotron 3 Nano and Super on Nebius Token Factory read; Tavily fetches the manufacturer's current pages; code
diffs the values) and reports, per item: no_change, changed (a value on the current sheet differs), discontinued
(the maker says so, quoted), or unverified (nothing could be confirmed). Local runs write runs/watch reports;
--post is for a local app without controller authority. Cloud workers require --controller and --lease,
enforce their assigned allowance locally, then return sealed usage and evidence through signed callbacks.
Only the controller can settle accounting and publish after cloud completion is independently observed.

Once a day the app server launches this script as a Nebius Serverless Job with --post to the public app
(api/daily_recheck.py); see deploy/nebius/recheck-job.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api import watch_store  # noqa: E402
from api.pipeline.cases import all_cases, mock_ready  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402
from api.schemas import Result  # noqa: E402
from api.readiness import invalid_reasons  # noqa: E402

STATUS_ORDER = ("discontinued", "changed", "unverified", "no_change")


def summarize(case: dict, res: Result | None) -> dict:
    """One line per item: the worst thing the re-check found, with its quote and source."""
    item = {"id": case["id"], "number": case.get("number"), "product": case.get("product"), "title": case["title"],
            "approved": (case.get("watch") or {}).get("approved")}
    if res is None:
        return {**item, "status": "unverified", "detail": "The re-check could not run for this item (see the run log)."}
    if reasons := invalid_reasons(res):
        return {**item, "status": "unverified", "detail": "The re-check is incomplete; inspect the run diagnostics.",
                "diagnostics": reasons, "cost_usd": res.fresh_model_cost_usd, "web_credits": res.fresh_web_credits,
                "duration_ms": res.duration_ms}
    status, detail, source, quote = "no_change", "Matches the manufacturer's current documents.", None, None
    for f in res.findings:
        if f.check == "status" and f.verdict == "fail":
            status, detail, quote = "discontinued", f.detail, f.quote
            source = f.evidence[0].url if f.evidence else None
            break
        if f.check == "currency" and f.verdict == "outdated" and status != "discontinued":
            status, detail = "changed", f.detail
            source = f.evidence[0].url if f.evidence else None
        elif f.check in ("currency", "status") and f.verdict == "unverified" and status == "no_change":
            status, detail = "unverified", f.detail
    if not {"currency", "status"} <= {f.check for f in res.findings} and status == "no_change":
        status, detail = "unverified", "The re-check did not complete both currency and status checks."
    fix = next((f.fix for f in res.findings if f.fix), None)
    candidate = next((c for c in fix.candidates if c.passes), None) if fix else None
    replacement = (fix.suggest or candidate.name) if candidate else None
    return {**item, "status": status, "detail": detail, "quote": quote, "source": source,
            "replacement": replacement, "decision": res.decision, "cost_usd": round(res.cost_usd, 6),
            "web_credits": res.web_credits, "duration_ms": res.duration_ms}


async def check(ids: list[str]):
    cases = all_cases()
    unknown = [i for i in ids if i not in cases]
    if unknown:
        sys.exit(f"Unknown items: {unknown}")
    if not settings.live:
        ids = [i for i in ids if mock_ready(cases[i])]
    started = time.perf_counter()
    run = Run(ids, delay_ms=0, refresh_web=True)
    await execute(run)
    items = [summarize(cases[i], run.results.get(i)) for i in ids]
    items.sort(key=lambda i: STATUS_ORDER.index(i["status"]))
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner": os.environ.get("RECHECK_RUNNER", "local"),
        "mode": settings.mode, "run_id": run.id,
        "job_name": os.environ.get("JOB_NAME"), "duration_ms": int((time.perf_counter() - started) * 1000),
        "models": settings.models,
        "items": items,
    }
    return report, run


async def main(ids: list[str], post: str | None) -> int:
    report, run = await check(ids)
    items = report["items"]
    folder = settings.runs_dir / "watch"
    watch_store.report(report)

    print(f"\nmode={settings.mode}  run={run.id}  runner={report['runner']}\n")
    for i in items:
        print(f"  {i['status']:<13} {i.get('number') or i['id']:<14} {i.get('product') or i['title']:<28} {i['detail'][:70]}")
        if i.get("replacement"):
            print(f"  {'':<13} {'':<14} replacement: {i['replacement']}")
    print(f"\nwrote {folder / 'latest.json'}")

    if post:
        token = settings.secret("admin_token")
        if not token:
            sys.exit("--post needs ADMIN_TOKEN (the app accepts reports with the X-Admin-Token header)")
        url = post.rstrip("/") + "/api/watch/report"
        r = httpx.post(url, json=report, headers={"X-Admin-Token": token}, timeout=30)
        print(f"posted re-check report: HTTP {r.status_code}")
        if r.is_error:
            return 1
    return 0 if all(i["status"] != "unverified" or not settings.live for i in items) else 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ids", nargs="*", help="item ids to re-check (default: every watched item)")
    p.add_argument("--post", help="base URL of the running app; the report is posted there with ADMIN_TOKEN")
    p.add_argument("--controller", help="HTTPS controller URL for a leased cloud worker")
    p.add_argument("--lease", help="controller-issued worker lease ID")
    args = p.parse_args()
    if args.controller or args.lease:
        if not args.controller or not args.lease or args.ids or args.post:
            p.error("Use --controller and --lease together, without --ids or --post")
        from api.job_worker import run as run_worker
        sys.exit(asyncio.run(run_worker(args.controller, args.lease)))
    if os.environ.get("JOB_NAME") and settings.live:
        sys.exit("Live cloud workers require a controller-issued lease; no provider call was made")
    ids = args.ids or sorted(i for i, c in all_cases().items() if c.get("watch"))
    if not ids:
        sys.exit("Nothing to re-check: no item has \"watch\" in data/cases/cases.json and no --ids given")
    sys.exit(asyncio.run(main(ids, args.post)))
