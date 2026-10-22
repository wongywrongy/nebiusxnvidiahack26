"""Steps 2 and 3: page triage (Nano) and extraction of requirements and claims (Super)."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Optional

from ..config import settings
from ..llm import router
from ..schemas import ClaimsOut, PageLabel, RequirementsOut, Selection, TriageOut, Usage

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


def page_batches(pages: list[dict], limit: int):
    """Cover complete pages in bounded overlapping chunks, keeping original page/source metadata."""
    limit = min(limit, 12000)
    batch, size = [], 0
    for page in pages:
        text, start = page["text"], 0
        while start < len(text):
            end = min(start + limit, len(text))
            if end < len(text):
                boundary = max(text.rfind("\n", start + limit // 2, end), text.rfind(" ", start + limit // 2, end))
                if boundary > start:
                    end = boundary + 1
            chunk = {**page, "text": text[start:end]}
            if batch and size + len(chunk["text"]) > 12000:
                yield batch
                batch, size = [], 0
            batch.append(chunk)
            size += len(chunk["text"])
            if end == len(text):
                break
            start = end - min(256, limit // 8)
    if batch:
        yield batch


async def extract_claims(case_id: Optional[str], pages: list[dict], labels: TriageOut, properties: list[str]) -> tuple[ClaimsOut, list[Usage]]:
    usage, outputs, kept, identities = [], [], {}, []
    ambiguous = False
    texts = {p["page"]: p["text"] for p in pages}
    for text in page_batches(pages, settings.max_page_chars):
        out, u = await _read_claims(case_id, text, properties)
        usage.append(u)
        outputs.append(out)
        extracted = len(out.claims)
        for c in out.claims:
            if not c.variant and (scope := re.search(r"^((?:non[\s-]*configurable|configurable|optional)[^:]{0,100}):", _plain(c.quote or ""), re.I)):
                c.variant = scope[1].strip()
        out.claims = [c for c in out.claims if c.property in properties and c.page in texts and quoted(c.quote, texts[c.page])
                      and value_quoted(c.value, c.quote, c.property) and metric_quoted(c.property, c.quote) and unit_quoted(c.unit, c.quote)
                      and (not c.variant or quoted(c.variant, c.quote or ""))]
        if out.claims:
            names = [out.model, out.family, *[c.model or c.product for c in out.claims], out.product]
            identity = next((name for name in names if name and any(model_quoted(name, p["text"]) for p in text)), "")
            if not identity:
                ambiguous = True
            identities.append(identity)
            ambiguous |= any((c.model and not (model_quoted(identity, c.model) and model_quoted(c.model, identity)))
                             or not (model_quoted(identity, c.product) or model_quoted(c.product, identity)
                                     or family_member(c.product, identity)) for c in out.claims)
        metrics.count("claims_extracted", "claims_kept", extracted, len(out.claims))
        for c in out.claims:
            key = (c.property, json.dumps(c.value, sort_keys=True), c.unit, c.page, c.quote, c.variant)
            kept.setdefault(key, c)
    result = outputs[0].model_copy(deep=True) if outputs else ClaimsOut(product="", manufacturer="", claims=[])
    for field in ("model", "document_revision", "family"):
        values = {getattr(o, field) for o in outputs if getattr(o, field)}
        setattr(result, field, next(iter(values)) if len(values) == 1 else None)
    if result.model and not any(model_quoted(result.model, p["text"]) for p in pages):
        result.model = None
    if result.document_revision and not any(revision_supported(result.document_revision, p["text"]) for p in pages):
        result.document_revision = None
    family = next((o for o in outputs if o.family == result.family and o.family_quote), None)
    if family and any(quoted(family.family_quote, p["text"]) for p in pages) and family_member(family.family, family.family_quote):
        result.family_quote = family.family_quote
    else:
        result.family = result.family_quote = None
    selections = [o.selection for o in outputs if o.selection and selection_supported(o.selection, texts)]
    result.selection = selections[0] if selections and len({s.model for s in selections}) == 1 else None
    if not result.selection and result.model and any(re.search(r"\bexample\s*:", p["text"], re.I) for p in pages) and not any(
            model_quoted(result.model, re.split(r"\bexample\s*:", p["text"], maxsplit=1, flags=re.I)[0]) for p in pages):
        result.model = result.family
    ambiguous |= bool(identities and any(not (model_quoted(identities[0], other) and
                        model_quoted(other, identities[0])) for other in identities[1:]))
    ambiguous |= bool(result.selection and any(not model_quoted(identity, result.selection.model) for identity in identities))
    if ambiguous:
        # Mixed product/assembly bundles need explicit attribution before their properties can be combined.
        result.selection = None
    elif result.selection:
        result.model = result.selection.model
    result.claims = list(kept.values())
    ids = set()
    for n, c in enumerate(result.claims):
        c.selection_quote = None
        wide = (scope_is_product_wide(c.scope, c.scope_quote, c.quote) and c.page in texts
                and quoted(c.scope_quote, texts[c.page]))
        if ambiguous or not c.variant and not wide:
            c.variant = c.variant or c.quote
        if ambiguous:
            c.scope = "unknown"
        if not ambiguous and c.variant and result.selection and model_quoted(c.variant, result.selection.model):
            c.selection_quote = result.selection.quote
        if c.id in ids:
            c.id = f"{c.id}-chunk-{n}"
        ids.add(c.id)
    return result, usage


async def _read_claims(case_id, text, properties):
    messages = [
        {
            "role": "user",
            "content": (
                "Extract the product's stated properties from this submittal. "
                f"Return only these property names, with exactly these spellings and meanings: {json.dumps({p: _label(p) for p in properties})}. "
                "Read every supplied page, including tables and notes. For a listed system, record its system number as model. "
                "For a product, record its short printed product/model identifier as model, not a rewritten marketing title. "
                "A product identifier names the product; selection separately proves a chosen ordering configuration. "
                "Separately identify the printed family and family_quote. Do not treat a blank catalog field or an ordering example as a selected model. "
                "Keep each test/rating metric distinct; never relabel a different metric to fit a requested name. "
                "Do not dump option tables. Omit SKU-dependent table values unless an exact submitted SKU is identified. "
                "A blank catalog-number field or an ordering example is not a submitted SKU selection. "
                "For other stated alternatives, retain distinct values without repeating the same value for every option. "
                "Set variant to the exact quoted option/configuration phrase whenever a value is limited to that option. "
                "Set scope and scope_quote from the full applicability statement; scope_quote must contain the value quote, "
                "not just a table heading. Use product_wide only for unqualified product properties, not selectable options. "
                "Return selection only when submitted evidence explicitly marks a selected/submitted/specified configuration, with its page and exact quote. "
                "Record the page and a short supporting quote for each claim, and the revision or date printed on the data sheet. "
                "Copy each quote verbatim as one contiguous substring from that page; never paraphrase or join separate passages. "
                "Omit properties that are not stated instead of returning null claims. "
                "For lists, put each distinct standard or certification identifier in its own array entry. "
                "For covered pipe types, quote the enumerated penetrating-item list, not the wall studs or sleeves.\n\n"
                + json.dumps(text)
            ),
        }
    ]
    class ClaimsRead(ClaimsOut):
        @classmethod
        def model_json_schema(cls, **kwargs):
            schema = super().model_json_schema(**kwargs)
            schema["$defs"]["Claim"]["properties"]["property"]["enum"] = properties
            return schema
    return await router.call("extract_claims", ClaimsRead, messages, {"case_id": case_id})


def scope_is_product_wide(scope: str, scope_quote: Optional[str], value_quote: Optional[str]) -> bool:
    return bool(scope == "product_wide" and quoted(value_quote, scope_quote or "")
                and not re.search(r"\b(optional|options?|selected|non[\s-]*configurable)\b|"
                                  r"\bonly\s+(?:for\s+)?(?:model|sku|driver|configuration)\b|"
                                  r"\b(?:model|sku|driver|configuration)\s+\S+\s+only\b", scope_quote or "", re.I))


def selection_supported(selection: Selection, pages: dict[int, str]) -> bool:
    text = pages.get(selection.page, "")
    quote = selection.quote
    normalized = _plain(text)
    start = normalized.find(_plain(quote))
    prefix = normalized[max(0, start - 80):start]
    label = re.search(r"\b(selected|submitted|specified)(?:\s+(?:model|sku|configuration|driver|product|catalog number))?\s*[:=]", quote, re.I)
    selected = re.split(r";|\r?\n|\.(?=\s|$)", quote[label.end():].strip(), maxsplit=1)[0] if label else ""
    return (quoted(quote, text) and model_quoted(selection.model, quote)
            and model_quoted(selection.model, selected)
            and not re.search(r"\b(example|sample|not|if|or|either|maybe)\b|e\.g\.", quote, re.I)
            and not re.search(r"\b(example|sample)\b[^.!?]{0,80}$", prefix, re.I))


def revision_supported(value: str, text: str) -> bool:
    if not quoted(value, text):
        return False
    return bool(re.search(r"\brev(?:ision)?\b|\b\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}\b|"
                          r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b.*\d{2}", value, re.I))


# PDF text and model output often differ only in typography: ligatures (ﬁ), dashes, curly quotes, ™/®.
_TYPO = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
                       "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2122": "", "\u00ae": "", "\u00a0": " "})


def _plain(text: str) -> str:
    text = re.sub(r"\\[nrt]", " ", text.translate(_TYPO))
    text = re.sub(r"(?<!\w)\*\*(?=\S)([^\r\n]*?\S)\*\*(?!\w)", r"\1", text)
    return " ".join(unicodedata.normalize("NFKC", text).split())


def quoted(quote: Optional[str], text: str) -> bool:
    """Exact text after whitespace/escaped whitespace and typographic normalization."""
    quote = _plain(quote or "")
    return bool(quote) and quote in _plain(text)


def model_quoted(model: str, text: str) -> bool:
    model = re.sub(r"[^\w+/]", "", _plain(model).casefold())
    if not model:
        return False
    pattern = r"(?<![\w+])" + r"[\s_.-]*".join(map(re.escape, model)) + r"(?![\w+]|[-_/][\w+])"
    return re.search(pattern, _plain(text).casefold()) is not None


def family_member(family: str, text: str) -> bool:
    if model_quoted(family, text):
        return True
    # Numeric form-factor prefixes/suffixes can surround a letter-only series name.
    return bool(re.fullmatch(r"[A-Za-z]{2,}", family) and
                re.search(r"(?<![\w+])\d*" + re.escape(family) + r"\d*(?![\w+])", _plain(text), re.I))


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
    patterns = {
        "lumens": r"\blumens?\b|\blm\b(?!\s*[/p]\s*w)",
        "watts": r"\b(?:watts?|wattage)\b|(?<![a-z/])w\b",
        "warranty_years": r"\bwarranty\b",
        "astm_g21_rating": r"\bg[\W_]*21\b|fung(?:al|us)|mold",
        "macadam_steps": r"macadam|\bsdcm\b",
    }
    if property in patterns:
        if property == "watts":
            text = re.sub(r"lm\s*/\s*w|lumens?\s+per\s+watt|\blpw\b", "", text, flags=re.I)
        return bool(re.search(patterns[property], text, re.I))
    return True


def unit_quoted(unit: Optional[str], quote: Optional[str]) -> bool:
    if not unit:
        return True
    aliases = {"hr": r"h(?:ours?|rs?)?", "yr": r"y(?:ears?|rs?)", "lm": r"lm|lumens?",
               "w": r"w|watts?|wattage", "lm/w": r"lm\s*/\s*w|lpw", "%": r"%|percent",
               "steps": r"steps?|sdcm", "rating": r"rating|class"}
    pattern = aliases.get(unit.lower(), re.escape(unit).replace(r"\ ", r"\s*"))
    return bool(re.search(r"(?<![a-z])(?:" + pattern + r")(?![a-z])", _plain(quote or ""), re.I))


def value_quoted(value, quote: Optional[str], property: str = "") -> bool:
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
        actual = bounds.get(match[1], match[1] or "")
        prefix = _plain(quote or "")[:match.start()].lower()
        suffix = _plain(quote or "")[match.end():].lower()
        postfix = re.match(r"\s*(?:cri|hours?|years?|hrs?|yrs?|%|g/l)?\s*(minimum|maximum)\b", suffix)
        if not actual and postfix:
            actual = ">=" if postfix[1] == "minimum" else "<="
        for words, symbol in ((r"greater than or equal to|at least|minimum(?: of)?", ">="),
                              (r"less than or equal to|at most|up to|not (?:to )?exceed|maximum(?: of)?", "<="),
                              (r"less than|under", "<"), (r"greater than|more than|over", ">"), (r"approximately|about", "~")):
            if not actual and re.search(r"(?:" + words + r")[\s:=]*$", prefix):
                actual = symbol
        # A named maximum/minimum is the quoted limit itself, not an observation somewhere below/above it.
        limit_metric = ("_max_" in property and actual == "<=") or ("_min_" in property and actual == ">=")
        if to_number(match[2]) == number and (actual == wanted or not wanted and limit_metric):
            return True
    return False


def all_product_data(pages: list[dict]) -> TriageOut:
    """Labels for a document already known to be one product's data (a fix candidate): no triage call needed."""
    return TriageOut(pages=[PageLabel(page=p["page"], kind="product_data") for p in pages])
