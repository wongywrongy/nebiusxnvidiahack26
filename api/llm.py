"""Model router.

Every model call in the pipeline goes through `router.call(task, schema, messages, ctx)`.
The router picks the Nemotron tier for the task, asks for JSON that matches `schema`,
validates it, retries once, then fails the step, and logs tokens, latency and cost.

Mock mode answers from `data/fixtures/<case_id>.json` so the pipeline runs with no API calls.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from . import cache
from .config import settings
from .schemas import Usage

T = TypeVar("T", bound=BaseModel)

# Which tier does each task use. Change routing here, nowhere else.
TASK_TIER: dict[str, str] = {
    "triage": "nano",
    "plan_queries": "nano",
    "extract_requirements": "super",
    "extract_claims": "super",
    "verify": "super",
    "report": "super",
}
RATE_LIMIT_RETRIES = 3  # on 429, back off 1s, 2s, 4s

# Which fixture key answers each task in mock mode.
FIXTURE_KEY = {
    "triage": "triage",
    "extract_claims": "claims",
    "verify": "verify",
    "report": "report",
}


class LLMError(RuntimeError):
    pass


def _cost(tier: str, tin: int, tout: int) -> float:
    pin, pout = settings.prices.get(tier, (0.0, 0.0))
    return round((tin * pin + tout * pout) / 1_000_000, 6)


def _rejects_format(e: Exception) -> bool:
    """True only when the server said no to the response_format itself (400 naming it)."""
    from openai import BadRequestError

    msg = str(e).lower()
    return isinstance(e, BadRequestError) and any(w in msg for w in ("response_format", "json_schema", "schema"))


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return m.group(1) if m else text


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
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            if not settings.nebius_api_key:
                raise LLMError("NEBIUS_API_KEY is not set (live mode)")
            self._client = AsyncOpenAI(
                base_url=settings.nebius_base_url, api_key=settings.nebius_api_key, max_retries=0  # we retry 429s ourselves
            )
        return self._client

    async def call(
        self,
        task: str,
        schema: type[T],
        messages: list[dict[str, Any]],
        ctx: Optional[dict[str, Any]] = None,
    ) -> tuple[T, Usage]:
        ctx = ctx or {}
        tier = TASK_TIER[task]
        if not settings.live:
            return self._mock(task, tier, schema, messages, ctx)

        last_err: Optional[Exception] = None
        for attempt in range(2):  # one retry, then the step fails
            try:
                return await self._live(task, tier, schema, messages, retry_note=last_err if attempt else None)
            except (ValidationError, json.JSONDecodeError) as e:
                last_err = e
        raise LLMError(f"{task}: no valid JSON after one retry: {last_err}")

    # ---------- mock ----------

    def _mock(self, task, tier, schema, messages, ctx) -> tuple[Any, Usage]:
        t0 = time.perf_counter()
        if task == "extract_requirements":
            payload = load_spec_fixture(ctx["section"])
        else:
            fixture = load_fixture(ctx["case_id"])
            key = FIXTURE_KEY.get(task, task)
            payload = fixture.get(key)
            if payload is None:
                payload = _default_payload(task, ctx)
        obj = schema.model_validate(payload)
        tin = sum(len(json.dumps(m.get("content", ""))) for m in messages) // 4
        tout = len(obj.model_dump_json()) // 4
        usage = Usage(
            task=task,
            tier=tier,
            model=settings.models[tier],
            input_tokens=tin,
            output_tokens=tout,
            cost_usd=_cost(tier, tin, tout),
            latency_ms=int((time.perf_counter() - t0) * 1000),
            cached=True,
        )
        return obj, usage

    # ---------- live ----------

    async def _create(self, **kw):
        """chat.completions.create with exponential backoff on 429. Other errors pass through."""
        from openai import RateLimitError

        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                return await self.client.chat.completions.create(**kw)
            except RateLimitError:
                if attempt == RATE_LIMIT_RETRIES:
                    raise
                await asyncio.sleep(2**attempt)

    async def _live(self, task, tier, schema, messages, retry_note=None) -> tuple[Any, Usage]:
        model = settings.models[tier]
        schema_json = schema.model_json_schema()
        msgs = [
            {
                "role": "system",
                "content": "Reply with JSON only. It must match this JSON schema:\n" + json.dumps(schema_json),
            },
            *messages,
        ]
        if retry_note:
            msgs.append({"role": "user", "content": f"Your last reply was invalid: {retry_note}. Return corrected JSON only."})

        key = {"model": model, "messages": msgs}
        hit = cache.get("llm", key)
        if hit:
            obj = schema.model_validate(hit["obj"])
            return obj, Usage(**{**hit["usage"], "cached": True})

        t0 = time.perf_counter()
        fmt = "json_schema"
        try:
            resp = await self._create(
                model=model,
                messages=msgs,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema.__name__, "schema": schema_json},
                },
            )
        except Exception as e:
            # Some models do not support json_schema on Token Factory: fall back to json_object.
            # Anything else (auth, network, a 400 about something else) is a real error.
            if not _rejects_format(e):
                raise
            fmt = "json_object"
            resp = await self._create(model=model, messages=msgs, temperature=0, response_format={"type": "json_object"})
        text = resp.choices[0].message.content or ""
        obj = schema.model_validate(json.loads(_strip_fences(text)))
        tin = resp.usage.prompt_tokens if resp.usage else 0
        tout = resp.usage.completion_tokens if resp.usage else 0
        usage = Usage(
            task=task,
            tier=tier,
            model=model,
            input_tokens=tin,
            output_tokens=tout,
            cost_usd=_cost(tier, tin, tout),
            latency_ms=int((time.perf_counter() - t0) * 1000),
            format=fmt,
        )
        cache.put("llm", key, {"obj": obj.model_dump(), "usage": usage.model_dump()})
        return obj, usage


def _default_payload(task: str, ctx: dict) -> dict:
    """Reasonable answers when a fixture omits a task (mock mode only)."""
    if task == "report":
        summary = "" if ctx.get("case_id") else (
            "Mock mode has no recorded answers for this PDF, so no values were read from it. Run in live mode to check it.")
        return {"summary": summary, "note_to_subcontractor": "", "finding_titles": {}, "why_it_matters": {}}
    if task == "verify":
        return {"status": "unknown", "current_values": [], "source_urls": []}
    if task == "triage":
        return {"pages": [{"page": n, "kind": "product_data"} for n in ctx.get("pages", [])]}
    if task == "extract_claims":
        return {"product": ctx.get("name", "Uploaded document"), "manufacturer": "", "claims": []}
    raise LLMError(f"No fixture and no default for task {task}")


router = Router()
