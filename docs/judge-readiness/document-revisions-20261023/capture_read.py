"""Authorized targeted live reproduction; records metadata, never credentials or source bodies."""

import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from api.config import settings
from api.llm import router
from scripts.eval import main

if not settings.live:
    raise SystemExit("This diagnostic requires the authorized live profile")

original = router.call
reads = []


async def capture(task, schema, messages, context=None):
    output, usage = await original(task, schema, messages, context)
    if task == "verify":
        reads.append({"request": {"task": task, "context": context, "authorization": "REDACTED",
            "messages_sha256": hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
            "instruction": messages[0]["content"].split("\n\nSUBMITTED:\n", 1)[0]},
            "response": {"current_revision": output.current_revision, "status": output.status,
                         "current_values_returned": len(output.current_values)}, "usage": usage.model_dump()})
    return output, usage


router.call = capture
try:
    result = asyncio.run(main(["c03", "c07"], Path("/tmp/document-revision-final-live.json")))
finally:
    router.call = original
    Path(__file__).with_name("source-read-responses.json").write_text(json.dumps(reads, indent=2) + "\n")
raise SystemExit(result)
