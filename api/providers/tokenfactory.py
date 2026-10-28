"""Token Factory (Nemotron) through its OpenAI-compatible REST API, over httpx. Live calls only.

chat(task, messages, schema) picks the model for the task from config, asks for JSON
(json_schema, or json_object when the server rejects json_schema), validates it with Pydantic
and retries once. 401/403/429 raise AuthError/RateLimited: no format fallback, no retry around them
(429 gets a short backoff first). Temperature 0, disk cache, budget charged, one log line per call.

Nemotron 3 is a reasoning model: it thinks before it answers unless asked not to. With THINKING=off (the
default) every call carries `reasoning_effort: none` and `chat_template_kwargs: {enable_thinking: false}`;
a server that rejects either field (400 naming it) is retried without that field. Whatever the server does,
the reply is read defensively: a `<think>...</think>` block or text around the JSON object is stripped, and
`reasoning_content` is never parsed as the answer. A reply cut off at MAX_OUTPUT_TOKENS while thinking was on
is retried once with thinking off instead of failing the step.
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
from ..schemas import ToolMessage, Usage
from . import AuthError, ProviderError, RateLimited, budget

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("speccheck.tokenfactory")

# Which configured model (settings.models role) answers each task. Change routing here, nowhere else.
TASK_MODEL: dict[str, str] = {
    "triage": "triage",
    "extract_requirements": "draft",
    "extract_claims": "extract",
    "product_type": "extract",
    "verify": "verify",
    "investigate": "verify",
    "replacement": "verify",
    "report": "write",
}
RATE_LIMIT_RETRIES = 3  # on 429, back off 1s, 2s, 4s, then RateLimited

# Public catalog, checked 2026-10-22; use binary K as a conservative upper bound.
# https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference
CONTEXT_LIMITS = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": 262 * 1024,
    "nvidia/nemotron-3-super-120b-a12b": 256 * 1024,
    "nvidia/Nemotron-3-Ultra-550b-a55b": 1024 * 1024,
}


async def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    for attempt in range(2):
        try:
            return await _request_once(method, path, body)
        except ProviderError as error:
            if attempt or method != "POST" or path != "/chat/completions" or not isinstance(error.__cause__, httpx.TimeoutException):
                raise
            log.warning("Model request timed out; retrying once with a fresh worst-case reservation")


TEMPLATE_TOKENS = 2048  # chat-template role headers and special tokens, generously


def input_token_bound(model: str, body: dict) -> int:
    """A hard upper bound on prompt tokens without a tokenizer: every byte-level BPE token covers at least one
    UTF-8 byte, so tokens <= bytes of the serialized request (+ template overhead), capped at the context.
    Reserving this instead of the whole context keeps the worst case honest while letting a 1M-context model
    (Ultra) run under the same per-run caps."""
    size = len(json.dumps(body, ensure_ascii=False).encode("utf-8")) + TEMPLATE_TOKENS
    return min(CONTEXT_LIMITS[model], size)


async def _request_once(method: str, path: str, body: Optional[dict] = None) -> dict:
    """One HTTP call. 401/403 -> AuthError, 429 -> RateLimited, other errors -> ProviderError with the server's message."""
    ticket = None
    if method == "POST" and path == "/chat/completions":
        model = body.get("model")
        if model not in CONTEXT_LIMITS or model not in PRICES or type(body.get("max_tokens")) is not int or body["max_tokens"] <= 0:
            raise ProviderError("Cannot bound the cost of this model request")
        if "tools" in body and "response_format" in body:
            raise ProviderError("Tools and response_format must be separate requests")
        ticket = budget.reserve_payment(usd=cost(model, input_token_bound(model, body), body["max_tokens"]))
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.request(method, settings.nebius_base_url.rstrip("/") + path, json=body,
                                headers={"Authorization": f"Bearer {settings.secret('nebius_api_key')}"})
    except httpx.HTTPError as e:
        if ticket:
            budget.settle_payment(ticket)
        raise ProviderError("Token Factory connection failed") from e
    except BaseException:
        if ticket:
            budget.settle_payment(ticket)
        raise
    if ticket and r.is_error:
        try:
            counts = _reported_usage(r.json())
        except ValueError:
            counts = None
        if counts is None:
            budget.unknown_usage(f"Token Factory HTTP {r.status_code}; billed usage was not reported")
        budget.settle_payment(ticket, **({"usd": cost(model, *counts)} if counts is not None else {}))
    if r.status_code in (401, 403):
        raise AuthError(f"Token Factory refused the key ({r.status_code}): check NEBIUS_API_KEY")
    if r.status_code == 429:
        raise RateLimited("Token Factory rate limit (429)")
    if r.is_error:
        raise ProviderError(f"Token Factory {r.status_code}: {r.text[:300]}")
    try:
        response = r.json()
    except ValueError as e:
        if ticket:
            budget.settle_payment(ticket)
        raise ProviderError("Token Factory returned invalid JSON") from e
    if ticket:
        counts = _reported_usage(response)
        budget.settle_payment(ticket, **({"usd": cost(model, *counts)} if counts is not None else {}))
    return response


def cost(model: str, tin: int, tout: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return round((tin * pin + tout * pout) / 1_000_000, 9)


def _rejects_format(e: Exception) -> bool:
    """True only when the server said no to the response_format itself (a 400 naming it)."""
    msg = str(e).lower()
    return isinstance(e, ProviderError) and " 400:" in msg and any(w in msg for w in ("response_format", "json_schema", "schema"))


# The two ways an OpenAI-compatible server is told not to think: the OpenAI-style field, and vLLM's template flag.
NO_THINK: dict[str, Any] = {"reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False}}


def _rejected_field(e: Exception) -> Optional[str]:
    """The NO_THINK field a 400 complained about, if any: it is dropped and the call is retried."""
    msg = str(e).lower()
    if not (isinstance(e, ProviderError) and " 400:" in msg):
        return None
    return next((f for f in NO_THINK if f in msg or f.replace("_", " ") in msg), None)


THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.S)


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return m.group(1) if m else text


def extract_json(text: Optional[str]) -> str:
    """The JSON object in a reply: thinking blocks, code fences and any prose around the object are dropped.

    A model that was asked not to think usually returns bare JSON; one that thought anyway may return
    `<think>...</think>{...}`, or `Here is the JSON:\\n{...}`. Everything from the first `{` to the last `}` is kept.
    """
    text = THINK_BLOCK.sub("", text or "").strip()
    text = _strip_fences(text)
    if text.startswith("{") or text.startswith("["):
        return text
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else text


def _reply_text(choice: dict) -> Optional[str]:
    """The answer field only: `reasoning_content` (vLLM's parsed thinking) is never read as the answer."""
    return (choice.get("message") or {}).get("content")


def _reasoning_tokens(resp: dict) -> int:
    details = ((resp.get("usage") or {}).get("completion_tokens_details") or {})
    return int(details.get("reasoning_tokens") or 0)


def _reported_usage(resp: dict) -> tuple[int, int] | None:
    usage = resp.get("usage") if isinstance(resp, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    values = tuple(usage.get(k) for k in ("prompt_tokens", "completion_tokens"))
    return values if all(type(n) is int and n >= 0 for n in values) else None


def _token_usage(resp: dict) -> tuple[int, int]:
    values = _reported_usage(resp)
    if values is None:
        budget.unknown_usage("Token Factory did not report valid usage; fresh spend is incomplete")
        return 0, 0
    return values


async def _create(**body) -> dict:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return await _request("POST", "/chat/completions", body)
        except RateLimited:
            if attempt == RATE_LIMIT_RETRIES:
                raise RateLimited(f"Token Factory rate limit (429) after {RATE_LIMIT_RETRIES} retries") from None
            await asyncio.sleep(2**attempt)


async def _create_no_think(no_think: dict[str, Any], **body) -> tuple[dict, dict[str, Any]]:
    """One completion with the no-think fields, dropping any field the server rejects. Returns (response, fields kept)."""
    fields = dict(no_think)
    while True:
        try:
            return await _create(**body, **fields), fields
        except ProviderError as e:
            bad = _rejected_field(e)
            if bad is None or bad not in fields:
                raise
            log.info("server rejected %s; retrying without it", bad)
            del fields[bad]


async def chat(task: str, messages: list[dict[str, Any]], schema: type[T], *, thinking: Optional[str] = None) -> tuple[T, Usage]:
    last: Optional[Exception] = None
    for attempt in range(2):  # one retry on invalid JSON, then the step fails
        try:
            return await _once(task, messages, schema, retry_note=last, thinking=thinking)
        except (ValidationError, json.JSONDecodeError) as e:
            last = e
    raise ProviderError(f"{task}: no valid JSON after one retry: {last}")


async def _once(task, messages, schema, retry_note=None, thinking: Optional[str] = None) -> tuple[Any, Usage]:
    role = TASK_MODEL[task]
    model = settings.models[role]
    thinking = thinking or settings.thinking_for(task)
    schema_json = schema.model_json_schema()
    msgs = [
        {"role": "system", "content": "Reply with JSON only. It must match this JSON schema:\n" + json.dumps(schema_json)},
        *messages,
    ]
    if retry_note:
        msgs.append({"role": "user", "content": f"Your last reply was invalid: {retry_note}. Return corrected JSON only."})

    key = {"base_url": settings.nebius_base_url, "model": model, "messages": msgs, "schema": schema_json,
           "thinking": thinking, "max_tokens": settings.max_output_tokens}
    if hit := cache.get("llm", key):
        if hit.get("usage_complete") is False:
            budget.unknown_usage("Cached Token Factory response has incomplete usage")
        return schema.model_validate(hit["obj"]), Usage(**{**hit["usage"], "cached": True})

    if model not in PRICES:  # cost would read $0 and no cap could hold
        raise ProviderError(f"No price for {model} in api/config.py PRICES: refusing the live call")
    pin, pout = PRICES[model]
    # Early rejection only; _request reserves the full model context before every HTTP attempt.
    budget.check_usd((len(json.dumps(msgs)) / 2 * pin + settings.max_output_tokens * pout) / 1e6, real=True)
    t0 = time.perf_counter()
    no_think = NO_THINK if thinking == "off" else {}
    body = dict(model=model, messages=msgs, temperature=0, max_tokens=settings.max_output_tokens)
    fmt = "json_schema"
    try:
        resp, kept = await _create_no_think(no_think, **body, response_format={
            "type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema_json}})
    except Exception as e:
        if not _rejects_format(e):  # auth, rate limit, network, a 400 about something else: real errors
            raise
        fmt = "json_object"
        resp, kept = await _create_no_think(no_think, **body, response_format={"type": "json_object"})
    tin, tout = _token_usage(resp)
    usage = Usage(task=task, tier=role, model=model, input_tokens=tin, output_tokens=tout, cost_usd=cost(model, tin, tout),
                  latency_ms=int((time.perf_counter() - t0) * 1000), format=fmt, reasoning_tokens=_reasoning_tokens(resp),
                  thinking="off" if kept else ("on" if thinking == "on" else "server-default"))
    log.info("%s model=%s in=%d out=%d reasoning=%d ms=%d cost=$%.6f format=%s thinking=%s", task, model, tin, tout,
             usage.reasoning_tokens, usage.latency_ms, usage.cost_usd, fmt, usage.thinking)
    choice = resp["choices"][0]
    if choice.get("finish_reason") == "length":
        if thinking != "off":  # the budget went on thinking: once more, asking for no thinking
            log.info("%s hit MAX_OUTPUT_TOKENS with thinking on; retrying with thinking off", task)
            return await _once(task, messages, schema, retry_note, thinking="off")
        raise ProviderError(f"{task}: reply hit MAX_OUTPUT_TOKENS ({settings.max_output_tokens}); "
                            f"{usage.reasoning_tokens} of {tout} output tokens were reasoning")
    obj = schema.model_validate(json.loads(extract_json(_reply_text(choice))))
    saved = {"obj": obj.model_dump(), "usage": usage.model_dump(), "usage_complete": _reported_usage(resp) is not None}
    cache.put("llm", key, saved)
    if retry_note:
        # A successful repair also answers the original request; repeats should not pay to repair it again.
        cache.put("llm", {**key, "messages": msgs[:-1]}, saved)
    return obj, usage


async def list_models() -> list[str]:
    return sorted(m["id"] for m in (await _request("GET", "/models"))["data"])


async def chat_tools(task: str, messages: list[dict[str, Any]], tools: list[dict]) -> tuple[ToolMessage, Usage]:
    """Native tool calls, deliberately separate from structured response_format requests."""
    role = TASK_MODEL[task]
    model = settings.models[role]
    body = dict(model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0,
                max_tokens=settings.max_output_tokens)
    if len(tools) == 1 and tools[0]['function']['name'] == 'finish':
        body['tool_choice'] = {'type': 'function', 'function': {'name': 'finish'}}
    thinking = settings.thinking_for(task)
    no_think = NO_THINK if thinking == "off" else {}
    key = {"base_url": settings.nebius_base_url, **body, "thinking": thinking}
    if hit := cache.get("llm_tools", key):
        if hit.get("usage_complete") is False:
            budget.unknown_usage("Cached Token Factory response has incomplete usage")
        return ToolMessage.model_validate(hit["message"]), Usage(**{**hit["usage"], "cached": True})
    if model not in PRICES:
        raise ProviderError(f"No price for {model} in api/config.py PRICES: refusing the live call")
    pin, pout = PRICES[model]
    budget.check_usd((len(json.dumps(body)) / 2 * pin + settings.max_output_tokens * pout) / 1e6, real=True)
    t0 = time.perf_counter()
    resp, kept = await _create_no_think(no_think, **body)
    tin, tout = _token_usage(resp)
    usage = Usage(task=task, tier=role, model=model, input_tokens=tin, output_tokens=tout,
                  cost_usd=cost(model, tin, tout), latency_ms=int((time.perf_counter() - t0) * 1000),
                  format="tools", thinking="off" if kept else ("on" if thinking == "on" else "server-default"),
                  reasoning_tokens=_reasoning_tokens(resp))
    log.info("%s model=%s in=%d out=%d ms=%d cost=$%.6f format=tools", task, model, tin, tout,
             usage.latency_ms, usage.cost_usd)
    try:
        choice = resp["choices"][0]
        usage.finish_reason = choice.get("finish_reason")
        if choice.get("finish_reason") == "length":
            raise ProviderError(f"{task}: reply hit MAX_OUTPUT_TOKENS ({settings.max_output_tokens})")
        message = ToolMessage.model_validate({**choice["message"], "tool_calls": choice["message"].get("tool_calls") or []})
    except (KeyError, IndexError, ValidationError) as e:
        raise ProviderError(f"{task}: invalid tool reply") from e
    cache.put("llm_tools", key, {"message": message.model_dump(), "usage": usage.model_dump(),
                                 "usage_complete": _reported_usage(resp) is not None})
    return message, usage
