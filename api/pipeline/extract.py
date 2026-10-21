"""Steps 2 and 3: page triage (Nano) and extraction of requirements and claims (Super)."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Optional

from ..config import settings
from ..llm import router
from ..schemas import ClaimsOut, PageLabel, RequirementsOut, TriageOut, Usage

from . import metrics
from .spec_check import _label, _mentions, to_number


async def triage(case_id: Optional[str], pages: list[dict]) -> tuple[TriageOut, Usage]:
    preview = [{"page": p["page"], "text": p["text"][:1500]} for p in pages]
    messages = [
        {
            "role": "user",
            "content": ("Label each page of this construction submittal by kind. Continuation pages with performance "
                        "tables, options, or system notes belong to the same document kind as their first page. "
                        "Use other only for blank or unrelated pages.\n" + json.dumps(preview)),
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


async def extract_requirements(section: str, spec_text: str, title: str = "") -> tuple[RequirementsOut, Usage]:
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
                + (f"Section title: {title}\n" if title else "") + spec_text[:60000]
            ),
        }
    ]
    return await router.call("extract_requirements", RequirementsOut, messages, {"section": section})


async def extract_claims(case_id: Optional[str], pages: list[dict], labels: TriageOut, properties: list[str]) -> tuple[ClaimsOut, Usage]:
    useful = {l.page for l in labels.pages if l.kind != "other"}
    text = [{"page": p["page"], "text": p["text"][:settings.max_page_chars]} for p in pages if p["page"] in useful]
    messages = [
        {
            "role": "user",
            "content": (
                "Extract the product's stated properties from this submittal. "
                f"Use these property names and meanings where they apply: {json.dumps({p: _label(p) for p in properties})}. "
                "Read every supplied page, including tables and notes. For a listed system, record its system number as model. "
                "Keep each test/rating metric distinct; never relabel a different metric to fit a requested name. "
                "Do not dump option tables. Omit SKU-dependent table values unless an exact submitted SKU is identified. "
                "A blank catalog-number field or an ordering example is not a submitted SKU selection. "
                "For other stated alternatives, retain distinct values without repeating the same value for every option. "
                "Set variant to the exact quoted option/configuration phrase whenever a value is limited to that option. "
                "Record the page and a short supporting quote for each claim, and the revision or date printed on the data sheet. "
                "Copy each quote verbatim as one contiguous substring from that page; never paraphrase or join separate passages. "
                "Omit properties that are not stated instead of returning null claims. "
                "For lists, put each distinct standard or certification identifier in its own array entry. "
                "For covered pipe types, quote the enumerated penetrating-item list, not the wall studs or sleeves.\n\n"
                + json.dumps(text)
            ),
        }
    ]
    out, usage = await router.call("extract_claims", ClaimsOut, messages, {"case_id": case_id})
    for c in out.claims:
        if not c.variant and (scope := re.search(r"^((?:non[\s-]*configurable|configurable|optional)[^:]{0,100}):", _plain(c.quote or ""), re.I)):
            c.variant = scope[1].strip()
    # Evidence or nothing: a claim whose quote isn't on the page it cites (any page, if none) is dropped.
    texts = {p["page"]: p["text"] for p in pages}
    extracted = len(out.claims)
    out.claims = [c for c in out.claims if quoted(c.quote, texts[c.page] if c.page in texts else " ".join(texts.values()))
                  and value_quoted(c.value, c.quote) and metric_quoted(c.property, c.quote)
                  and (not c.variant or quoted(c.variant, c.quote or ""))]
    metrics.count("claims_extracted", "claims_kept", extracted, len(out.claims))
    return out, usage


# PDF text and model output often differ only in typography: ligatures (ﬁ), dashes, curly quotes, ™/®.
_TYPO = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
                       "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2122": "", "\u00ae": "", "\u00a0": " "})


def _plain(text: str) -> str:
    text = re.sub(r"\\[nrt]", " ", text.translate(_TYPO))
    return " ".join(unicodedata.normalize("NFKC", text).split())


def quoted(quote: Optional[str], text: str) -> bool:
    """Exact text after whitespace/escaped whitespace and typographic normalization."""
    quote = _plain(quote or "")
    return bool(quote) and quote in _plain(text)


def metric_quoted(property: str, quote: Optional[str]) -> bool:
    text = _plain(quote or "")
    lumen = re.fullmatch(r"l(\d+)_hours", property)
    if lumen:
        n = lumen[1]
        return bool(re.search(rf"\bl[\W_]*{n}\b|(?<!\d){n}\s*(?:%|percent\b)", text, re.I))
    if property in {"f_rating_hr", "t_rating_hr"}:
        return bool(re.search(rf"\b{property[0]}[\W_]*rat(?:ings?|ed)\b", text, re.I))
    if property == "cri":
        return bool(re.search(r"(?<![a-z])cri(?![a-z])|colou?r rendering", text, re.I))
    return True


def value_quoted(value, quote: Optional[str]) -> bool:
    """Require the stated value, including numeric bounds or categorical identifiers, in its quote."""
    if isinstance(value, list):
        return bool(value) and all(value_quoted(v, quote) for v in value)
    if value is None or isinstance(value, bool):
        return False
    number = to_number(value)
    if number is None:
        return _mentions(_plain(quote or ""), str(value))
    bounds = {"≤": "<=", "≥": ">="}
    bound = re.match(r"[<>]=?|[≤≥~]", str(value).strip())
    wanted = bounds.get(bound[0], bound[0]) if bound else ""
    for match in re.finditer(r"(?<![\w.])([<>]=?|[≤≥~])?\s*(-?\d[\d,]*(?:\.\d+)?(?:[- ]\d+/\d+|/\d+)?)(?![\d.])", _plain(quote or "")):
        if to_number(match[2]) == number and bounds.get(match[1], match[1] or "") == wanted:
            return True
    return False


def all_product_data(pages: list[dict]) -> TriageOut:
    """Labels for a document already known to be one product's data (a fix candidate): no triage call needed."""
    return TriageOut(pages=[PageLabel(page=p["page"], kind="product_data") for p in pages])
