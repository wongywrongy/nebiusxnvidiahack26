"""Steps 2 and 3: page triage (Nano) and extraction of requirements and claims (Super)."""

from __future__ import annotations

import json
import unicodedata
from typing import Optional

from ..config import settings
from ..llm import router
from ..schemas import ClaimsOut, PageLabel, RequirementsOut, TriageOut, Usage

MAX_PAGE_CHARS = 6000


async def triage(case_id: Optional[str], pages: list[dict]) -> tuple[TriageOut, Usage]:
    preview = [{"page": p["page"], "text": p["text"][:1500]} for p in pages]
    messages = [
        {
            "role": "user",
            "content": "Label each page of this construction submittal by kind.\n" + json.dumps(preview),
        }
    ]
    return await router.call("triage", TriageOut, messages, {"case_id": case_id, "pages": [p["page"] for p in pages]})


def checklist_path(section: str):
    return settings.data_dir / "requirements" / f"{section.replace(' ', '_')}.json"


async def requirements_for(section: str, spec_text: str) -> tuple[RequirementsOut, Optional[Usage]]:
    """The reviewed checklist for this section when there is one (data/requirements/<section>.json, written by
    scripts/draft_requirements.py and checked by a person), else a model extraction of the spec text."""
    path = checklist_path(section)
    if settings.live and path.exists():
        return RequirementsOut.model_validate(json.loads(path.read_text())), None
    if settings.live and not spec_text.strip():
        raise RuntimeError(f"No text for spec {section}: run scripts/fetch_docs.py (data/raw/ is empty)")
    return await extract_requirements(section, spec_text)


async def extract_requirements(section: str, spec_text: str) -> tuple[RequirementsOut, Usage]:
    messages = [
        {
            "role": "user",
            "content": (
                f"From spec section {section}, list the requirements a manufacturer's product data sheet or a listed "
                "system drawing can be checked against: numbers, ratings, listings, test standards, warranty. "
                "Leave out installation, execution, scheduling, contractor qualifications and anything only the "
                "drawings or the site can show. Give the paragraph number for each. "
                "Use snake_case property names with the unit in the name (t_rating_hr, voc_g_per_l, cri, warranty_years). "
                "Use operator eq_ref when one property must equal another (value = the other property name). "
                "Set applies_to to product_data or system_drawing when a requirement only makes sense for one.\n\n"
                + spec_text[:60000]
            ),
        }
    ]
    return await router.call("extract_requirements", RequirementsOut, messages, {"section": section})


async def extract_claims(case_id: Optional[str], pages: list[dict], labels: TriageOut, properties: list[str]) -> tuple[ClaimsOut, Usage]:
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
    out, usage = await router.call("extract_claims", ClaimsOut, messages, {"case_id": case_id})
    # Evidence or nothing: a claim whose quote isn't on the page it cites (any page, if none) is dropped.
    texts = {p["page"]: p["text"] for p in pages}
    out.claims = [c for c in out.claims if quoted(c.quote, texts[c.page] if c.page in texts else " ".join(texts.values()))]
    return out, usage


# PDF text and model output often differ only in typography: ligatures (ﬁ), dashes, curly quotes, ™/®.
_TYPO = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
                       "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2122": "", "\u00ae": "", "\u00a0": " "})


def _plain(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).translate(_TYPO).split())


def quoted(quote: Optional[str], text: str) -> bool:
    """True when quote appears in text, ignoring whitespace runs and typography (ligatures, dashes, curly quotes)."""
    return bool(quote and quote.strip()) and _plain(quote) in _plain(text)


def all_product_data(pages: list[dict]) -> TriageOut:
    """Labels for a document already known to be one product's data (a fix candidate): no triage call needed."""
    return TriageOut(pages=[PageLabel(page=p["page"], kind="product_data") for p in pages])
