"""Read-only, dated Tavily billing audit. Prints counters only; never settles a payment."""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

import httpx

sys.path.insert(0, str(Path.cwd()))
from api.config import settings


def wallet_digest():
    path = settings.campaign_budget_file.resolve()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        value = connection.execute("SELECT data FROM campaign WHERE id=1").fetchone()[0]
    return hashlib.sha256(value.encode()).hexdigest()


if not settings.keys_present["TAVILY_API_KEY"]:
    raise SystemExit(json.dumps(settings.keys_present))

before = wallet_digest()
body = {"limit": 10000, "start_date": "2026-10-01", "end_date": "2026-10-23", "filter_by_api_key": True}
headers = {"Authorization": "Bearer " + settings.secret("tavily_api_key")}
with httpx.Client(timeout=35) as client:
    response = client.post("https://api.tavily.com/logs", headers=headers, json=body)
    assert response.status_code == 200, f"Logs returned HTTP {response.status_code}; no settlement performed"
    data = response.json()
    logs = data["logs"]
    assert len(logs) == data["count"] < body["limit"], "Log window may be truncated"
    by_day = defaultdict(lambda: defaultdict(float))
    for row in logs:
        credits = row["credits"]
        assert type(credits) in (int, float) and math.isfinite(credits) and credits >= 0
        day = datetime.fromisoformat(row["timestamp"]).astimezone(timezone.utc).date().isoformat()
        by_day[day][row["endpoint"]] += credits
    usage = client.get("https://api.tavily.com/usage", headers=headers)
    assert usage.status_code == 200, f"Usage returned HTTP {usage.status_code}; no settlement performed"
    counters = usage.json()

assert before == wallet_digest(), "Wallet changed during lookup; inspect before interpreting results"
print(json.dumps({"scope": "Read-only log/counter observation; no payment settlement",
    "observed_at": datetime.now(timezone.utc).isoformat(), "request_body": body, "log_count": len(logs),
    "credits_by_utc_day_endpoint": dict(by_day), "latest_log": max(row["timestamp"] for row in logs),
    "key_usage": counters["key"]["usage"], "account_usage": counters["account"]["plan_usage"],
    "wallet_unchanged": True}, indent=2))
