"""Token Factory (Nemotron) through its OpenAI-compatible REST API, over httpx. Live calls only.

chat(task, messages, schema) picks the model for the task from config, asks for JSON
(json_schema, or json_object when the server rejects json_schema), validates it with Pydantic
and retries once. 401/403/429 raise AuthError/RateLimited: no format fallback, no retry around them
(429 gets a short backoff first). Temperature 0, disk cache, budget charged, one log line per call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Optional, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .. import cache
from ..config import PRICES, settings
from ..schemas import Usage
from . import AuthError, ProviderError, RateLimited, budget

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("speccheck.tokenfactory")

# Which configured model (settings.models role) answers each task. Change routing here, nowhere else.
TASK_MODEL: dict[str, str] = {
    "triage": "triage",
    "extract_requirements": "extract",
    "extract_claims": "extract",
    "verify": "verify",
    "report": "write",
}
RATE_LIMIT_RETRIES = 3  # on 429, back off 1s, 2s, 4s, then RateLimited



async def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """One HTTP call. 401/403 -> AuthError, 429 -> RateLimited, other errors -> ProviderError with the server's message."""
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.request(method, settings.nebius_base_url.rstrip("/") + path, json=body,
                            headers={"Authorization": f"Bearer {settings.secret('nebius_api_key')}"})
    if r.status_code in (401, 403):
        raise AuthError(f"Token Factory refused the key ({r.status_code}): check NEBIUS_API_KEY")
    if r.status_code == 429:
        raise RateLimited("Token Factory rate limit (429)")
    if r.is_error:
        raise ProviderError(f"Token Factory {r.status_code}: {r.text[:300]}")
    return r.json()


def cost(model: str, tin: int, tout: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return round((tin * pin + tout * pout) / 1_000_000, 6)


def _rejects_format(e: Exception) -> bool:
    """True only when the server said no to the response_format itself (a 400 naming it)."""
    msg = str(e).lower()
    return isinstance(e, ProviderError) and " 400:" in msg and any(w in msg for w in ("response_format", "json_schema", "schema"))


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return m.group(1) if m else text


async def _create(**body) -> dict:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return await _request("POST", "/chat/completions", body)
        except RateLimited:
            if attempt == RATE_LIMIT_RETRIES:
                raise RateLimited(f"Token Factory rate limit (429) after {RATE_LIMIT_RETRIES} retries") from None
            await asyncio.sleep(2**attempt)


async def chat(task: str, messages: list[dict[str, Any]], schema: type[T]) -> tuple[T, Usage]:
    last: Optional[Exception] = None
    for attempt in range(2):  # one retry on invalid JSON, then the step fails
        try:
            return await _once(task, messages, schema, retry_note=last)
        except (ValidationError, json.JSONDecodeError) as e:
            last = e
    raise ProviderError(f"{task}: no valid JSON after one retry: {last}")


async def _once(task, messages, schema, retry_note=None) -> tuple[Any, Usage]:
    role = TASK_MODEL[task]
    model = settings.models[role]
    schema_json = schema.model_json_schema()
    msgs = [
        {"role": "system", "content": "Reply with JSON only. It must match this JSON schema:\n" + json.dumps(schema_json)},
        *messages,
    ]
    if retry_note:
        msgs.append({"role": "user", "content": f"Your last reply was invalid: {retry_note}. Return corrected JSON only."})

    key = {"model": model, "messages": msgs, "schema": schema_json}
    if hit := cache.get("llm", key):
        return schema.model_validate(hit["obj"]), Usage(**{**hit["usage"], "cached": True})

    if model not in PRICES:  # cost would read $0 and no cap could hold
        raise ProviderError(f"No price for {model} in api/config.py PRICES: refusing the live call")
    pin, pout = PRICES[model]
    # ponytail: input estimated at 2 chars per token (real is ~4), so the worst case is over, never under.
    budget.check_usd((len(json.dumps(msgs)) / 2 * pin + settings.max_output_tokens * pout) / 1e6, real=True)
    t0 = time.perf_counter()
    fmt = "json_schema"
    try:
        resp = await _create(model=model, messages=msgs, temperature=0, max_tokens=settings.max_output_tokens, response_format={
            "type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema_json}})
    except Exception as e:
        if not _rejects_format(e):  # auth, rate limit, network, a 400 about something else: real errors
            raise
        fmt = "json_object"
        resp = await _create(model=model, messages=msgs, temperature=0, max_tokens=settings.max_output_tokens,
                             response_format={"type": "json_object"})
    tin = (resp.get("usage") or {}).get("prompt_tokens", 0)
    tout = (resp.get("usage") or {}).get("completion_tokens", 0)
    usage = Usage(task=task, tier=role, model=model, input_tokens=tin, output_tokens=tout, cost_usd=cost(model, tin, tout),
                  latency_ms=int((time.perf_counter() - t0) * 1000), format=fmt)
    budget.charge_usd(usage.cost_usd, real=True)  # paid even if the reply is invalid
    log.info("%s model=%s in=%d out=%d ms=%d cost=$%.6f format=%s", task, model, tin, tout, usage.latency_ms, usage.cost_usd, fmt)
    choice = resp["choices"][0]
    if choice.get("finish_reason") == "length":  # cut off: a retry would pay for the same cut-off again
        raise ProviderError(f"{task}: reply hit MAX_OUTPUT_TOKENS ({settings.max_output_tokens})")
    obj = schema.model_validate(json.loads(_strip_fences(choice["message"].get("content") or "")))
    cache.put("llm", key, {"obj": obj.model_dump(), "usage": usage.model_dump()})
    return obj, usage


async def list_models() -> list[str]:
    return sorted(m["id"] for m in (await _request("GET", "/models"))["data"])
