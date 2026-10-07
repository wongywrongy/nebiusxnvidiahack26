"""Live spike: list the Token Factory models, then one tiny call per configured model. Costs real tokens.

    python scripts/spike_models.py

Reports per model: whether it is in the account's model list, which response_format worked
(json_schema or the json_object fallback), latency and token counts. Responses are cached in
.cache/llm, so a re-run is free and shows cached=True.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from pydantic import BaseModel

os.environ["SPECCHECK_MODE"] = "live"  # before api.config is imported: fails fast, naming any missing key
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import PRICES, settings  # noqa: E402
from api.providers import tokenfactory  # noqa: E402

# One task per distinct configured model.
TASKS = {"triage": "triage", "extract_claims": "extract", "reconcile": "reconcile"}
MESSAGES = [{"role": "user", "content": "Firestop sealant, 2 hr F-rating, tested to ASTM E814. Extract the rating."}]
EST_IN, EST_OUT = 300, 1000  # schema prompt + message; output is generous because reasoning models think out loud


class Rating(BaseModel):
    product: str
    f_rating_hours: float
    standard: str


async def main() -> None:
    print(f"Endpoint: {settings.nebius_base_url}")
    available = await tokenfactory.list_models()  # free
    print(f"{len(available)} models on this account")
    total = 0.0
    for task, role in TASKS.items():
        model = settings.models[role]
        pin, pout = PRICES.get(model, (0.0, 0.0))
        total += (EST_IN * pin + EST_OUT * pout) / 1e6
        print(f"  {role:9} {model:45} {'listed' if model in available else 'NOT LISTED'}")
    print(f"Estimated cost: ~${total:.5f} (0.0 prices in api/config.py PRICES are placeholders)")
    if input("Run live? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")

    for task, role in TASKS.items():
        print(f"\n== {role}: {settings.models[role]}")
        try:
            obj, usage = await tokenfactory.chat(task, MESSAGES, Rating)
        except Exception as e:
            print(f"   ERROR {type(e).__name__}: {str(e)[:300]}")
            continue
        print(f"   result: {obj.model_dump()}")
        print(f"   format={usage.format}  latency={usage.latency_ms} ms  in={usage.input_tokens}  out={usage.output_tokens}"
              f"  cost=${usage.cost_usd:.6f}  cached={usage.cached}")


if __name__ == "__main__":
    asyncio.run(main())
