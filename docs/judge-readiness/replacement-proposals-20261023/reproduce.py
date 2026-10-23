"""Offline before/after and prompt capture; never calls a provider or settles a wallet."""

import ast
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path.cwd()))
from api import readiness
from api import schemas
from api.pipeline import extract
from api.schemas import ClaimsOut, Selection, Usage

folder = Path(__file__).resolve().parent
baseline = "7419dda"
source = subprocess.check_output(["git", "show", baseline + ":api/pipeline/extract.py"], text=True)
function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "selection_supported")
namespace = {"re": re, "Selection": Selection, "_plain": extract._plain,
             "quoted": extract.quoted, "model_quoted": extract.model_quoted}
exec(compile(ast.Module(body=[function], type_ignores=[]), "baseline-selection", "exec"), namespace)
rows = []
for label, model, quote, text, origin in [
    ("Real submitted selection", "ZX-12 D1", "Selected: ZX-12 D1", "Selected: ZX-12 D1.", "submitted"),
    ("Truncated submitted SKU", "ZX-12 D1", "Selected: ZX-12 D1", "Selected: ZX-12 D10. Other SKU: ZX-12 D1.", "submitted"),
    ("Printed catalog proposal", "ZX-12-D1", "Catalog number: ZX-12-D1", "Catalog number: ZX-12-D1.", "agent_proposal"),
    ("Invented catalog proposal", "ZX-12-D1", "Catalog number: ZX-12-D1", "Catalog number: ZX-12-D10.", "agent_proposal"),
    ("Ordering example", "ZX-12-D1", "Catalog number: ZX-12-D1", "Ordering example: Catalog number: ZX-12-D1.", "agent_proposal"),
]:
    selection = Selection(model=model, page=1, quote=quote, origin=origin)
    rows.append({"scenario": label, "source": text, "quote": quote,
        "before": namespace["selection_supported"](selection, {1: text}),
        "after_original": extract.selection_supported(selection, {1: text}),
        "after_replacement": extract.selection_supported(selection, {1: text}, allow_proposal=True)})
assert [r["before"] for r in rows] == [True, True, False, False, False]
assert [r["after_original"] for r in rows] == [True, False, False, False, False]
assert [r["after_replacement"] for r in rows] == [True, False, True, False, False]

captured = []
async def capture(task, schema, messages, ctx):
    captured.append({"task": task, "messages": messages, "schema": schema.model_json_schema()})
    return ClaimsOut(product="Synthetic", manufacturer="Synthetic", claims=[]), Usage(task=task, tier="extract", model="synthetic")

async def prompts():
    original = extract.router.call
    extract.router.call = capture
    try:
        pages = [{"page": 1, "text": "Model ZX-12. Catalog number: ZX-12-D1. D1 dimming to 2%."}]
        old_schemas = subprocess.check_output(["git", "show", baseline + ":api/schemas.py"], text=True)
        classes = [node for node in ast.parse(old_schemas).body if isinstance(node, ast.ClassDef) and node.name in ("Selection", "ClaimsOut")]
        model_namespace = dict(vars(schemas))
        exec(compile(ast.Module(body=classes, type_ignores=[]), "baseline-models", "exec"), model_namespace)
        read = next(node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_read_claims")
        baseline_namespace = {**vars(extract), "ClaimsOut": model_namespace["ClaimsOut"]}
        exec(compile(ast.Module(body=[read], type_ignores=[]), "baseline-prompt", "exec"), baseline_namespace)
        await baseline_namespace["_read_claims"](None, pages, ["dim_min_percent"])
        for mode in (False, True):
            await extract._read_claims(None, pages, ["dim_min_percent"], propose=mode)
    finally:
        extract.router.call = original

asyncio.run(prompts())
assert captured[0] == captured[1], "Ordinary extraction request/schema changed from baseline"
for name, request in zip(("prompt-before", "prompt-after"), (captured[0], captured[2])):
    (folder / (name + ".json")).write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n")
    (folder / (name + ".txt")).write_text(request["messages"][0]["content"] + "\n")
(folder / "before-after.json").write_text(json.dumps({
    "observed_at": datetime.now(timezone.utc).isoformat(), "scope": "Offline synthetic boundary probe and stubbed prompt capture; no provider response",
    "baseline_commit": baseline, "current_code_hash": readiness.manifest()["code_hash"], "rows": rows,
    "ordinary_request_matches_baseline": True, "paid_requests": 0, "settlements": 0}, indent=2) + "\n")
print("Offline before/after assertions and prompt capture passed; no provider request or settlement.")
