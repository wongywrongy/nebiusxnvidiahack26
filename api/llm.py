"""Model router.

Every model call in the pipeline goes through `router.call(task, schema, messages, ctx)`.
Live: providers.tokenfactory.chat (model per task, JSON validated, cached, costed).
Mock: answers from `data/fixtures/<case_id>.json` so the pipeline runs with no API calls or keys.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from .config import settings
from .providers import budget, tokenfactory
from .schemas import ToolMessage, Usage

T = TypeVar("T", bound=BaseModel)

class LLMError(RuntimeError):
    pass


def load_fixture(case_id: Optional[str]) -> dict:
    """A case's recorded responses. None (an upload that matches no case) has none: every task uses its default."""
    if case_id is None:
        return {}
    path = settings.fixtures_dir / f"{case_id}.json"
    if not path.exists():
        raise LLMError(f"No fixture for case {case_id} at {path}")
    return json.loads(path.read_text())


def load_spec_fixture(section: str) -> dict:
    path = settings.fixtures_dir / "specs" / f"{section.replace(' ', '_')}.json"
    return json.loads(path.read_text())


class Router:
    async def call(
        self,
        task: str,
        schema: type[T],
        messages: list[dict[str, Any]],
        ctx: Optional[dict[str, Any]] = None,
    ) -> tuple[T, Usage]:
        if task == "investigate":
            if settings.live:
                return await tokenfactory.chat_tools(task, messages, ctx["tools"])
            return self._mock_tools(messages, ctx or {})
        if settings.live:
            return await tokenfactory.chat(task, messages, schema, thinking=(ctx or {}).get("thinking"))
        return self._mock(task, schema, messages, ctx or {})

    def _mock(self, task, schema, messages, ctx) -> tuple[Any, Usage]:
        t0 = time.perf_counter()
        if task == "extract_requirements":
            payload = load_spec_fixture(ctx["section"])
        else:
            fixture = load_fixture(ctx["case_id"])
            payload = fixture.get("claims" if task == "extract_claims" else ctx.get("fixture_key", task))
            if payload is None:
                payload = _default_payload(task, ctx)
        obj = schema.model_validate(payload)
        role = tokenfactory.TASK_MODEL[task]
        model = settings.models[role]
        tin = sum(len(json.dumps(m.get("content", ""))) for m in messages) // 4
        tout = len(obj.model_dump_json()) // 4
        usage = Usage(task=task, tier=role, model=model, input_tokens=tin, output_tokens=tout,
                      cost_usd=tokenfactory.cost(model, tin, tout), latency_ms=int((time.perf_counter() - t0) * 1000),
                      cached=True, thinking=ctx.get("thinking", settings.thinking_for(task)))
        budget.check_usd()
        budget.charge_usd(usage.cost_usd, real=False)
        return obj, usage

    def _mock_tools(self, messages: list[dict], ctx: dict) -> tuple[ToolMessage, Usage]:
        fixture = load_fixture(ctx.get("case_id")).get("investigate", {})
        index = sum(m.get("role") == "tool" for m in messages)
        steps = fixture.get("steps", [])
        step = steps[index] if index < len(steps) else {
            "tool": "finish", "args": fixture.get("final", {"found": False, "status": "unknown", "note": "No mock investigation recorded."})}
        message = ToolMessage.model_validate({"tool_calls": [{"id": f"mock-{index}", "function": {
            "name": step["tool"], "arguments": json.dumps(step["args"])}}]})
        model = settings.models["verify"]
        tin, tout = len(json.dumps(messages)) // 4, len(message.model_dump_json()) // 4
        usage = Usage(task="investigate", tier="verify", model=model, input_tokens=tin, output_tokens=tout,
                      cost_usd=tokenfactory.cost(model, tin, tout), cached=True, format="tools", thinking=settings.thinking_for("investigate"))
        budget.check_usd()
        budget.charge_usd(usage.cost_usd, real=False)
        return message, usage


def _default_payload(task: str, ctx: dict) -> dict:
    """Reasonable answers when a fixture omits a task (mock mode only)."""
    if task == "report":
        summary = "" if ctx.get("case_id") else (
            "Mock mode has no recorded answers for this PDF, so no values were read from it. Run in live mode to check it.")
        return {"summary": summary, "note_to_subcontractor": "", "finding_titles": {}, "why_it_matters": {}}
    if task == "verify":
        return {"status": "unknown", "current_values": [], "source_urls": []}
    if task == "product_type":
        return {"product_type": None}
    if task == "replacement":
        return {"product": None, "quote": None}
    if task == "triage":
        return {"pages": [{"page": n, "kind": "product_data"} for n in ctx.get("pages", [])]}
    if task == "extract_claims":
        return {"product": ctx.get("name", "Uploaded document"), "manufacturer": "", "claims": []}
    raise LLMError(f"No fixture and no default for task {task}")


router = Router()
