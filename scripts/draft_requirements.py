"""Draft each spec section's requirement checklist with Nemotron Super, for a person to review. Costs real tokens
(one call per section, about $0.01 each; cached, so a re-run is free).

    python scripts/fetch_docs.py            # the spec PDFs must be in data/raw/specs/
    python scripts/draft_requirements.py    # writes data/requirements/<section>.draft.json

Review a draft: delete what a data sheet can't show, fix property names, values and severities, then save it as
data/requirements/<section>.json. Live runs use the reviewed file and skip the extraction call, so every submittal is
checked against the same list a reviewer signed off on, which is how a real engineer works from a spec.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ["SPECCHECK_MODE"] = "live"  # before api.config is imported: fails fast, naming any missing key
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.pipeline.cases import all_specs  # noqa: E402
from api.pipeline.extract import checklist_path, extract_requirements  # noqa: E402
from api.pipeline.ingest import load_spec_text  # noqa: E402
from api.providers import budget  # noqa: E402


async def main() -> None:
    budget.LEDGER.set(budget.Ledger())
    for section, spec in all_specs().items():
        text = load_spec_text(section, spec)
        if not text.strip():
            print(f"skip  {section}: no spec PDF in data/raw/ (run scripts/fetch_docs.py)")
            continue
        out, usage = await extract_requirements(section, text)
        dest = checklist_path(section).with_suffix(".draft.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({"_note": f"Draft from {usage.model}. Review, then save as {checklist_path(section).name}.",
                                    **out.model_dump()}, indent=2))
        print(f"\n{section}  {len(out.requirements)} requirements  {len(text):,} chars of spec"
              f"{' (truncated at 60,000)' if len(text) > 60000 else ''}  ${usage.cost_usd:.4f}  -> {dest.relative_to(ROOT)}")
        for r in out.requirements:
            print(f"  {r.paragraph:<10} {r.property:<24} {r.operator:<7} {str(r.value):<20} {r.severity:<8} {r.text[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
