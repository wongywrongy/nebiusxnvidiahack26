"""Live spike: one tiny call to each Nemotron tier through the router. Costs real tokens.

    python scripts/spike_models.py

Reports per model: which response_format worked (json_schema or the json_object fallback),
latency and token counts. Responses are cached in .cache/llm, so a re-run is free and shows cached=True.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.llm import router  # noqa: E402

TIERS = ["nano", "super", "ultra"]
MESSAGES = [{"role": "user", "content": "Firestop sealant, 2 hr F-rating, tested to ASTM E814. Extract the rating."}]
EST_IN, EST_OUT = 300, 1000  # schema prompt + message; output is generous because reasoning models think out loud


class Rating(BaseModel):
    product: str
    f_rating_hours: float
    standard: str


def estimate() -> float:
    total = 0.0
    for tier in TIERS:
        pin, pout = settings.prices[tier]
        cost = (EST_IN * pin + EST_OUT * pout) / 1e6
        total += cost
        print(f"  {tier:5} {settings.models[tier]:45} ~{EST_IN}+{EST_OUT} tok  ~${cost:.5f}")
    print(f"  total ~${total:.5f}  (super/ultra prices in config.py are 0.0 PLACEHOLDERS, real cost is a few cents at most)")
    return total


async def main() -> None:
    if not settings.nebius_api_key:
        sys.exit("NEBIUS_API_KEY is not set (put it in .env)")
    print(f"Endpoint: {settings.nebius_base_url}\nEstimated cost for 3 calls:")
    estimate()
    if input("Run live? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")

    # Spy on the OpenAI client: the router silently falls back to json_object on any error, so record each attempt.
    attempts: list[tuple[str, str]] = []
    completions = router.client.chat.completions
    real_create = completions.create

    async def spy(**kw):
        fmt = kw["response_format"]["type"]
        try:
            resp = await real_create(**kw)
        except Exception as e:
            attempts.append((fmt, f"FAILED {type(e).__name__}: {str(e)[:200]}"))
            raise
        attempts.append((fmt, "ok"))
        return resp

    completions.create = spy

    for tier in TIERS:
        attempts.clear()
        print(f"\n== {tier}: {settings.models[tier]}")
        try:
            obj, usage = await router._live("spike", tier, Rating, MESSAGES)
        except Exception as e:
            print(f"   ERROR {type(e).__name__}: {str(e)[:300]}")
        else:
            print(f"   result: {obj.model_dump()}")
            print(f"   latency={usage.latency_ms} ms  in={usage.input_tokens}  out={usage.output_tokens}  cached={usage.cached}  format={usage.format}")
        for fmt, status in attempts:
            print(f"   response_format={fmt}: {status}")
        if not attempts:
            print("   (served from .cache/llm, delete it to re-test formats)")


if __name__ == "__main__":
    asyncio.run(main())
