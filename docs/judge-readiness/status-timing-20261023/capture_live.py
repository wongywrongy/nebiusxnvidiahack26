import asyncio
import hashlib
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
from api.providers import tokenfactory
from api.config import settings

if not settings.live:
    raise SystemExit("This diagnostic requires explicitly authorized live mode")
from scripts.eval import main

observations = []
original = tokenfactory._create_no_think


async def capture(no_think, **body):
    started = time.perf_counter()
    response, kept = await original(no_think, **body)
    choice = response["choices"][0]
    message = choice.get("message") or {}
    observations.append({
        "model": body["model"], "max_tokens": body["max_tokens"],
        "messages_sha256": hashlib.sha256(json.dumps(body["messages"], sort_keys=True).encode()).hexdigest(),
        "schema": (body.get("response_format") or {}).get("json_schema", {}).get("name"),
        "tools_sent": bool(body.get("tools")), "no_think_fields_kept": sorted(kept),
        "finish_reason": choice.get("finish_reason"), "usage": response.get("usage"),
        "content_chars": len(message.get("content") or ""), "tool_calls": len(message.get("tool_calls") or []),
        "latency_seconds": round(time.perf_counter() - started, 3),
    })
    return response, kept


tokenfactory._create_no_think = capture
try:
    result = asyncio.run(main(["c07"], Path("docs/judge-readiness/status-timing-20261023/live/score.json")))
finally:
    Path("docs/judge-readiness/status-timing-20261023/live/response-metadata.json").write_text(
        json.dumps({"scope": "Actual fresh response metadata only; no messages, credentials or response body",
                    "responses": observations}, indent=2) + "\n")
raise SystemExit(result)
