"""Owner-only deployment smoke check. Two inputs share one run's USD cap and one item's web allowance."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pymupdf as fitz

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_CAPS = {"budget_usd_per_run": 3, "budget_usd_per_day": 8, "budget_tavily_credits_per_item": 60,
                   "budget_tavily_credits_per_day": 600, "max_concurrency": 2}


def check(client: httpx.Client, *, timeout: float = 600, poll_s: float = 1, preflight_only: bool = False) -> list[str]:
    failures = []

    def request(method, path, **kwargs):
        try:
            response = client.request(method, path, **kwargs)
            if response.status_code != 200:
                failures.append(f"{method} {path}: HTTP {response.status_code}")
                return None
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
            return data
        except (httpx.HTTPError, ValueError):
            failures.append(f"{method} {path}: connection failed or invalid JSON")
            return None

    health = request("GET", "/api/health") or {}
    if health.get("mode") != "live":
        failures.append("Health must report mode: live; no scan was started.")
    keys = health.get("keys", {})
    if not keys or any(keys.get(k) is not True for k in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "ADMIN_TOKEN")) or any(v is not True for v in keys.values()):
        failures.append("Health must report every key present as true (never key values).")
    caps = health.get("caps", {})
    for name, ceiling in PRODUCTION_CAPS.items():
        value = caps.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= ceiling:
            failures.append(f"Health cap {name} must be positive and no greater than {ceiling}.")
    if health.get("scan_shared_item_budget") is not True:
        failures.append("Deployment lacks the shared smoke budget; refusing two paid inputs.")
    for path in ("/api/specs", "/api/scores"):
        request("GET", path)
    project = request("GET", "/api/project") or {}
    if project.get("mode") != "live":
        failures.append("Project must report mode: live.")
    try:
        watch = client.get("/api/watch")
        data = watch.json()
        if watch.status_code == 404:
            if not isinstance(data, dict) or not data.get("detail"):
                failures.append("Watch 404 must explain that no report exists yet.")
        elif watch.status_code != 200 or not isinstance(data, dict) or not data.get("checked_at") or not isinstance(data.get("items"), list):
            failures.append("Watch must return a report or a clear 404.")
    except (httpx.HTTPError, ValueError):
        failures.append("Watch request failed or returned invalid JSON.")
    if failures or preflight_only:
        return failures  # All preflight checks are read-only; never spend on a misconfigured deployment.

    print("Caps: " + json.dumps(caps, sort_keys=True))
    case = request("POST", "/api/inbox", json={"id": "c01"})
    if not case or case.get("id") != "c01":
        return failures or ["Inbox did not return c01."]
    pdfs = list((ROOT / "tests" / "data").glob("*.pdf"))
    if not pdfs:
        return ["No smoke PDF in tests/data/; nothing was scanned."]
    pdf = min(pdfs, key=lambda p: p.stat().st_size)
    # A new, labelled probe proves provider access without discarding paid cached product readings.
    with fitz.open(pdf) as probe:
        probe[0].insert_text((36, 36), f"Deployment smoke probe {time.time_ns()}")
        payload = probe.tobytes()
    uploaded = request("POST", "/api/inbox", params={"name": pdf.name},
                       headers={"Content-Type": "application/pdf"}, content=payload)
    if not uploaded or not uploaded.get("id"):
        return failures or ["Upload did not return an inbox item."]
    ids = ["c01", uploaded["id"]]
    scan = request("POST", "/api/scan", json={"ids": ids, "delay_ms": 0, "shared_item_budget": True})
    if not scan or not scan.get("run_id"):
        return failures or ["Scan did not return a run id."]
    if scan.get("shared_item_budget") is not True:
        return ["Scan did not acknowledge the shared budget; no retry was made."]
    path = f"/api/runs/{scan['run_id']}/results"
    deadline = time.monotonic() + timeout
    results = {}
    while time.monotonic() < deadline:
        response = request("GET", path)
        if response is None:
            return failures
        results = {r.get("case_id"): r for r in response.get("results", [])}
        if all(cid in results for cid in ids) or response.get("done"):
            break
        time.sleep(poll_s)
    for cid in ids:
        result = results.get(cid)
        if result is None:
            failures.append(f"{cid}: no result before completion/timeout; inspect run {scan['run_id']} events.")
        elif result.get("error") or not result.get("findings"):
            failures.append(f"{cid}: result is an error or has no findings.")
        elif (result.get("validity") != "valid" or result.get("warnings") or result.get("diagnostics")
              or result.get("replayed_from")):
            failures.append(f"{cid}: invalid or replayed evidence cannot prove a fresh deployment check.")
    if result := results.get("c01"):
        if result.get("mode") != "live":
            failures.append("c01: expected live mode.")
    fresh = any(r.get("mode") == "live" and not r.get("replayed_from") and
                not u.get("cached", False) and u.get("model", "").lower().startswith("nvidia/") and
                "nemotron" in u.get("model", "").lower()
                for r in results.values() for u in r.get("usage", []))
    if not fresh:
        failures.append("Expected a non-cached live Nemotron call; cached traces or replays do not prove provider access.")
    if result := results.get(uploaded["id"]):
        if result.get("mode") != "live":
            failures.append("Upload ran in mock mode; enable public live uploads or supply the admin token.")
        if not any(c.get("quote") for c in result.get("claims", [])) and not any(
            f.get("verdict") == "unverified" for f in result.get("findings", [])
        ):
            failures.append("Upload: expected a quoted claim or an honest couldn't-confirm finding.")
    print(f"Run: {scan['run_id']} · inputs: c01 + {pdf.name} (stamped smoke probe) · shared item budget · no retries")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--admin-token", default=os.environ.get("ADMIN_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=600, help="maximum polling seconds (default 600)")
    parser.add_argument("--preflight-only", action="store_true", help="read-only health/configuration checks; never upload or scan")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error("Use the HTTP(S) base URL without credentials, query or fragment.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    headers = {"X-Admin-Token": args.admin_token} if args.admin_token else {}
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=30, follow_redirects=False) as client:
        failures = check(client, timeout=args.timeout, preflight_only=args.preflight_only)
    if failures:
        print("Smoke failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Read-only preflight passed; no scan was started." if args.preflight_only else
          "Smoke passed: live health/project, bounded fresh scan, PDF, specs, scores and watch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
