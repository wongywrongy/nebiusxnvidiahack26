"""Live spike: list the Token Factory models, then one tiny call per configured model. Costs real tokens.

    python scripts/spike_models.py            # asks before spending
    python scripts/spike_models.py --yes      # no prompt (CI, a fresh key)

Reports per model: whether it is in the account's model list, which response_format worked (json_schema or the
json_object fallback), whether the server honoured the no-thinking fields (THINKING=off), reasoning tokens, latency,
token counts and cost. Also lists every Nemotron model the account can see, so a newer one (Ultra, 3.5) is noticed.
Responses are cached in .cache/llm, so a re-run is free and shows cached=True.

Write anything surprising (a rejected field, reasoning tokens with thinking off, a missing model) in FEEDBACK.md:
that is the hackathon's feedback section.
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
from api.providers import budget, tokenfactory  # noqa: E402

# One task per distinct configured model.
TASKS = {"triage": "triage", "extract_claims": "extract"}
MESSAGES = [{"role": "user", "content": "Firestop sealant, 2 hr F-rating, tested to ASTM E814. Extract the rating."}]
EST_IN, EST_OUT = 300, 1000  # schema prompt + message; output is generous because reasoning models think out loud


class Rating(BaseModel):
    product: str
    f_rating_hours: float
    standard: str


async def main() -> None:
    budget.LEDGER.set(budget.Ledger())
    print(f"Endpoint: {settings.nebius_base_url}   THINKING={settings.thinking}")
    available = await tokenfactory.list_models()  # free
    print(f"{len(available)} models on this account")
    nemotron = [m for m in available if "nemotron" in m.lower()]
    print("Nemotron models visible:\n  " + "\n  ".join(nemotron))
    total = 0.0
    for task, role in TASKS.items():
        model = settings.models[role]
        pin, pout = PRICES.get(model, (0.0, 0.0))
        total += (EST_IN * pin + EST_OUT * pout) / 1e6
        print(f"  {role:9} {model:45} {'listed' if model in available else 'NOT LISTED'}")
    print(f"Estimated cost: ~${total:.5f}")
    if "--yes" not in sys.argv and input("Run live? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")

    for task, role in TASKS.items():
        print(f"\n== {role}: {settings.models[role]}")
        try:
            obj, usage = await tokenfactory.chat(task, MESSAGES, Rating)
        except Exception as e:
            print(f"   ERROR {type(e).__name__}: {str(e)[:300]}")
            continue
        print(f"   result: {obj.model_dump()}")
        print(f"   format={usage.format}  thinking={usage.thinking}  reasoning_tokens={usage.reasoning_tokens}"
              f"  latency={usage.latency_ms} ms  in={usage.input_tokens}  out={usage.output_tokens}"
              f"  cost=${usage.cost_usd:.6f}  cached={usage.cached}")
        if usage.thinking == "server-default":
            print("   NOTE the server rejected both no-think fields; thinking is whatever the model defaults to")
        if usage.thinking == "off" and usage.reasoning_tokens:
            print("   NOTE reasoning tokens were billed although thinking was off: worth a FEEDBACK.md line")


if __name__ == "__main__":
    asyncio.run(main())
