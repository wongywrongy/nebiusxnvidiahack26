"""Steps 2 and 3: page triage (Nano) and extraction of requirements and claims (Super)."""

from __future__ import annotations

import json

from ..llm import router
from ..schemas import ClaimsOut, RequirementsOut, TriageOut, Usage

MAX_PAGE_CHARS = 6000


async def triage(case_id: str, pages: list[dict]) -> tuple[TriageOut, Usage]:
    preview = [{"page": p["page"], "text": p["text"][:1500]} for p in pages]
    messages = [
        {
            "role": "user",
            "content": "Label each page of this construction submittal by kind.\n" + json.dumps(preview),
        }
    ]
    return await router.call("triage", TriageOut, messages, {"case_id": case_id})


async def extract_requirements(section: str, spec_text: str) -> tuple[RequirementsOut, Usage]:
    messages = [
        {
            "role": "user",
            "content": (
                f"From spec section {section}, list every requirement a product submittal can be checked against. "
                "Use snake_case property names with the unit in the name (t_rating_hr, voc_g_per_l, cri, warranty_years). "
                "Use operator eq_ref when one property must equal another (value = the other property name).\n\n"
                + spec_text[:60000]
            ),
        }
    ]
    return await router.call("extract_requirements", RequirementsOut, messages, {"section": section})


async def extract_claims(case_id: str, pages: list[dict], labels: TriageOut, properties: list[str]) -> tuple[ClaimsOut, Usage]:
    useful = {l.page for l in labels.pages if l.kind != "other"}
    text = [{"page": p["page"], "text": p["text"][:MAX_PAGE_CHARS]} for p in pages if p["page"] in useful]
    messages = [
        {
            "role": "user",
            "content": (
                "Extract the product's stated properties from this submittal. "
                f"Use these property names where they apply: {', '.join(properties)}. "
                "Record the page and a short supporting quote for each claim, and the revision or date printed on the data sheet.\n\n"
                + json.dumps(text)
            ),
        }
    ]
    return await router.call("extract_claims", ClaimsOut, messages, {"case_id": case_id})
