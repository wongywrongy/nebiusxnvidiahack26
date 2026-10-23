"""Step 4b: check the submittal against the live web.

For one product: find the manufacturer's current document and product status with Tavily,
let Nemotron Super read what came back, then diff the values in plain code.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from ..config import settings
from ..llm import load_fixture, router
from ..providers import ProviderError, budget
from ..schemas import ClaimsOut, Compare, CompareRow, Evidence, Finding, Investigation, Usage, VerifyOut, VerificationProof
from ..web import WebClient, snapshot
from .extract import family_member, metric_quoted, model_quoted, page_batches, revision_supported, scope_is_product_wide, unit_quoted, value_quoted, quoted
from .investigate import investigate
from .spec_check import UNIT_TO_BASE, _fmt, _label, normalize, to_number
from . import metrics

LISTING_BODIES = ("ul.com", "intertek.com", "icc-es.org", "designlights.org", "energystar.gov")
TIER_RANK = {"manufacturer": 0, "listing_body": 1, "distributor": 2, "agency": 3, "archive": 4, "other": 5}


def classify(url: str, manufacturer_domains: list[str]) -> str:
    host = (urlparse(url).hostname or "").lower()
    if any(host == d or host.endswith("." + d) for d in manufacturer_domains):
        return "manufacturer"
    if "web.archive.org" in host:
        return "archive"
    if any(host == d or host.endswith("." + d) for d in LISTING_BODIES):
        return "listing_body"
    if host.endswith(".gov") or host.endswith(".edu"):
        return "agency"
    return "distributor"


def source_urls(results: list[dict], domains: list[str]) -> list[str]:
    ranked = sorted(results, key=lambda r: TIER_RANK[classify(r["url"], domains)])
    urls = list(dict.fromkeys(r["url"] for r in ranked))
    # Reserve a source slot for a status notice as well as product documentation.
    notice = next((r["url"] for r in ranked if classify(r["url"], domains) == "manufacturer" and
                   re.search(r"discontinu|end[-\s]+of[-\s]+life|obsolete|retire", r.get("title", "") + " " + r["url"], re.I)), None)
    selected = urls[:3]
    if notice and notice not in selected:
        selected[-1] = notice
    return selected


def _same(a, b, unit_a=None, unit_b=None) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        left = a if isinstance(a, list) else [a]
        right = b if isinstance(b, list) else [b]
        if len(left) == len(right) == 1:
            return _same(left[0], right[0], unit_a, unit_b)
        return sorted(map(str, left)) == sorted(map(str, right))
    if unit_a and unit_b and UNIT_TO_BASE.get(unit_a.lower(), (unit_a.lower(),))[0] != UNIT_TO_BASE.get(unit_b.lower(), (unit_b.lower(),))[0]:
        return False
    na, nb = normalize(a, unit_a), normalize(b, unit_b)
    bounds = lambda v: re.match(r"[<>]=?|[≤≥~]", str(v).strip())
    ba, bb = bounds(a), bounds(b)
    if bool(ba) != bool(bb) or ba and {"≤": "<=", "≥": ">="}.get(ba[0], ba[0]) != {"≤": "<=", "≥": ">="}.get(bb[0], bb[0]):
        return False
    if na is not None and nb is not None:
        return abs(na - nb) < 1e-9
    return str(a).strip().lower() == str(b).strip().lower()


def comparable_units(a, b) -> bool:
    def dimension(unit):
        unit = (unit or "").strip().lower()
        return UNIT_TO_BASE.get(unit, (unit,))[0]
    return dimension(a) == dimension(b)


def _unambiguous(values) -> dict:
    grouped = {}
    for value in values:
        if value.property == "document_revision" or getattr(value, "variant", None) and not getattr(value, "selection_quote", None):
            continue
        grouped.setdefault(value.property, []).append(value)
    return {prop: group[0] for prop, group in grouped.items()
            if all(_same(group[0].value, v.value) and group[0].unit == v.unit for v in group)}


async def verify(case: dict, submitted: ClaimsOut, *, on_step=None, on_warning=None, on_sources=None, on_proof=None
                 ) -> tuple[list[Finding], list[CompareRow], list[Usage], float, Investigation | None]:
    fx = case.get("fixture", case["id"])  # uploads: the matching case's fixture, or None
    web = WebClient(fx, on_step, on_warning)
    domains = case.get("manufacturer_domains", [])
    name = " ".join(x for x in [submitted.manufacturer, submitted.product, submitted.model or ""] if x)

    # 1. Search: current document, and product status.
    results = await web.search(f"{name} data sheet", include_domains=domains or None, include_domains_mode="prefer")
    model = (submitted.model or "").replace('"', '').strip()
    status_name = " ".join(x for x in [submitted.manufacturer, submitted.product, f'"{model}"' if model else ""] if x)
    for topic in ("general", "news"):
        results += await web.search(f"{status_name} discontinued OR replaced", topic=topic,
                                    include_published_date=True, exact_match=bool(model))
    if domains:
        label = case.get("product") or f"{submitted.manufacturer} {submitted.product}"
        results += await web.search(f"{label} discontinuation notice",
                                    include_domains=domains, include_domains_mode="prefer")
    # One bounded map attempt can find a PDF missed by search before escalating to the investigator.
    if domains and not any(classify(r["url"], domains) == "manufacturer" for r in results):
        try:
            with budget.credit_scope(5):  # at most 4 for an instructed map + 1 for extracting three URLs
                links = await web.map(f"https://{domains[0]}", instructions=f"Find the current PDF data sheet for {name}",
                                      limit=min(20, settings.map_limit), max_depth=1)
                links = sorted(dict.fromkeys(links), key=lambda url: not urlparse(url).path.lower().endswith(".pdf"))[:3]
                mapped = await web.extract(links)
        except (budget.BudgetExceeded, ProviderError) as error:
            await web.warn("verify.map", error)
            mapped = []  # keep the search evidence; an unsuccessful optional lookup cannot erase it
    else:
        mapped = []
    # 2. Extract the best few pages.
    selected = source_urls(results, domains)
    pages = await web.extract(selected)
    if len(pages) < len(selected):
        backfill = source_urls([r for r in results if r["url"] not in selected], domains)[:len(selected) - len(pages)]
        pages += await web.extract(backfill)
    pages += [p for p in mapped if p["url"] not in {p["url"] for p in pages}]
    titles = {r["url"]: r.get("title", "") for r in results}

    # 3. Super reads the sources; the quote gate runs before the investigator trigger.
    out, u = await read_sources(fx, submitted, pages, submitted_label=case.get("product"))
    usage = u
    if any(not value_quoted(pv.value, pv.quote, pv.property) for pv in out.current_values):
        out, u = await read_sources(fx, submitted, pages, correction=out, submitted_label=case.get("product"))
        usage += u
    confirmed = gate(out, pages, submitted=submitted)
    investigation = None
    comparable = bool(set(_unambiguous(submitted.claims)) & set(_unambiguous(out.current_values)))
    missing = set(_unambiguous(submitted.claims)) - set(_unambiguous(out.current_values))
    scripted = out.model_copy(deep=True)
    # A quoted revision or discontinuation already answered the scripted check.
    if (settings.live or load_fixture(fx).get("investigate")) and out.status != "discontinued" and (
        missing or out.current_revision is None and (not comparable or (out.status == "unknown" and
                                  not any(classify(r["url"], domains) == "manufacturer" for r in results))
    )):
        investigation = await investigate({**case, "unconfirmed_properties": sorted(missing)}, submitted, web)
        investigation.scripted = scripted
        usage += investigation._usage
        if investigation.outcome == "found":
            accepted = [p for p in investigation._pages if p["url"] == investigation._document_url]
            accepted += [p for p in pages if p["url"] not in {a["url"] for a in accepted}][:max(0, 3 - len(accepted))]
            newer = investigation._verified.model_copy(deep=True)
            try:
                newer, u = await read_sources(fx, submitted, accepted, investigated=True, submitted_label=case.get("product"))
                usage += u
            except (budget.BudgetExceeded, ProviderError) as error:
                await web.warn("verify.read", error)
            out = newer
            pages += investigation._pages
            titles[investigation._document_url] = investigation._document_title
            confirmed = gate(out, pages, submitted=submitted)

    evidence = [
        Evidence(tier=classify(p["url"], domains), title=titles.get(p["url"], p["url"]),
                 **{**snapshot(p["url"], p["raw_content"]),
                    **{k: p[k] for k in ("retrieved_at", "sha256", "archived_path", "cache_hit") if k in p}})
        for p in pages
    ]
    if on_sources:
        on_sources(pages)
    if on_proof:
        on_proof(VerificationProof(submitted=submitted.model_copy(deep=True), output=out.model_copy(deep=True), sources=evidence))
    findings, rows = compare(submitted, out, confirmed, evidence, pages)
    if investigation and investigation.outcome == "found":
        rescued = [r for r in rows if r.property in missing and any(
            p["url"] == r.source_url and quoted(r.quote, p["raw_content"]) for p in investigation._pages)]
        status_rescued = (out.status == "discontinued" and scripted.status != "discontinued" and any(
            quoted(out.status_quote, p["raw_content"]) for p in investigation._pages))
        investigation.resolution = ("problem_found" if status_rescued or any(r.changed for r in rescued) else
                                    "values_confirmed" if rescued else
                                    "revision_only" if not scripted.current_revision and out.current_revision else "not_resolved")
    return findings, rows, usage, web.credits, investigation


async def read_sources(fx, submitted: ClaimsOut, pages: list[dict], investigated=False,
                       correction: VerifyOut | None = None, *, submitted_label=None) -> tuple[VerifyOut, list[Usage]]:
    chunks = [[{**p, "raw_content": p["text"]} for p in batch]
              for batch in page_batches([{**p, "text": p["raw_content"]} for p in pages], settings.web_source_chars)]
    outputs, usage = [], []
    for batch in chunks or [[]]:
        out, u = await _read_sources(fx, submitted, batch, investigated, correction, submitted_label=submitted_label)
        outputs.append(out)
        usage.append(u)
    merged = outputs[0].model_copy(deep=True)
    merged.current_values = [v for out in outputs for v in out.current_values]
    revisions = {out.current_revision for out in outputs if out.current_revision}
    merged.current_revision = next(iter(revisions)) if len(revisions) == 1 else None
    statuses = {out.status for out in outputs if out.status != "unknown"}
    merged.status = next(iter(statuses)) if len(statuses) == 1 else "unknown"
    if merged.status != "unknown":
        status = next(out for out in outputs if out.status == merged.status)
        merged.status_quote, merged.status_date, merged.replacement = status.status_quote, status.status_date, status.replacement
        merged.status_family = status.status_family
    merged.source_urls = list(dict.fromkeys(url for out in outputs for url in out.source_urls))
    return merged, usage


async def _read_sources(fx, submitted, pages, investigated=False, correction=None, *, submitted_label=None):
    submitted_view = {
        "product": submitted.product,
        "manufacturer": submitted.manufacturer,
        "model": submitted.model,
        "family": submitted.family,
        "submitted_label": submitted_label,
        "document_revision": submitted.document_revision,
        "claims": [{"property": c.property, "value": c.value, "unit": c.unit}
                   for c in _unambiguous(submitted.claims).values()],
    }
    sources = [{"url": p["url"], "linked_from": p.get("requested_url") if p.get("requested_url") != p["url"] else None,
                "text": p["raw_content"]} for p in pages]
    feedback = ""
    if correction is not None:
        rejected = [pv.property for pv in correction.current_values if not value_quoted(pv.value, pv.quote, pv.property)]
        feedback = (f"\n\nPREVIOUS OUTPUT:\n{correction.model_dump_json()}\n"
                    f"Value quote validation rejected these properties: {json.dumps(rejected)}. "
                    "Read their source passages again and correct the quotes or omit the values. "
                    "Each quote must contain the stated value, including numeric bounds and each categorical identifier.")
    properties = sorted({c["property"] for c in submitted_view["claims"]})
    class SourceRead(VerifyOut):
        @classmethod
        def model_json_schema(cls, **kwargs):
            schema = super().model_json_schema(**kwargs)
            if properties:
                schema["$defs"]["PropertyValue"]["properties"]["property"]["enum"] = properties
            else:
                schema["properties"]["current_values"]["maxItems"] = 0
            return schema
    return await router.call(
        "verify",
        SourceRead,
        [
            {
                "role": "user",
                "content": (
                    "Compare the submitted product data with these current web sources. "
                    "Report product status, the current document revision exactly as printed, and the CURRENT value for each "
                    "submitted property you can find, each with the exact quote from the source that states it. "
                    "Return only properties in SUBMITTED.claims, copying their property names exactly. "
                    "Use documents for the exact submitted product/model or listed system, not a generic certificate. "
                    "For each value, give source_url and an exact identity_quote naming that source's model. "
                    "Set model to the exact short identifier from SUBMITTED.model (or family, then product if absent), "
                    "only when that identifier is actually printed in identity_quote. Do not replace it with a marketing title. "
                    "Those fields and model are mandatory evidence; omitted identity is rejected. "
                    "Set scope and scope_quote to the full applicability passage; never call an option-specific value product_wide. "
                    "scope_quote must include the value quote, not just a table heading. "
                    "Preserve a limiting option/SKU as variant; never compare a different configuration as product-wide. "
                    "Read status notices independently of data sheet values. A manufacturer's family-wide status notice "
                    "can apply to a member model without printing its full order code; establish that family relationship "
                    "using the submitted label and product/model names, and set status_family to its exact name in both. An unrelated product's values or active status "
                    "cannot establish this product's status. Quote the family notice when it applies. "
                    "Do not use certification/category codes or a catalog's Updated timestamp as a document revision. "
                    "Prefer the data sheet linked by the manufacturer's product page over a standalone search hit. "
                    "For each property, first locate a short verbatim quote stating its current value. "
                    "Copy the value from that quote, preserving any numeric bound. Never take the value from "
                    "a different passage than its quote. A related limit is not evidence for a different number. "
                    "Omit values you cannot support with that exact quote.\n\n"
                    f"SUBMITTED:\n{json.dumps(submitted_view)}\n\nSOURCES:\n{json.dumps(sources)}{feedback}"
                ),
            }
        ],
        {"case_id": fx, "fixture_key": "investigate_verify" if investigated else "verify"},
    )


def gate(out: VerifyOut, pages: list[dict], *, measure: bool = True, submitted: ClaimsOut | None = None) -> dict[str, str]:
    """Keep only what a fetched page actually quotes, for both scripted and investigated sources."""
    def same_product(page):
        if submitted is None:
            return True
        identifier = submitted.model or submitted.family or submitted.product
        return model_quoted(identifier, page["raw_content"])

    def source_of(quote, url=None, identity=True):
        return next((p["url"] for p in pages if (not url or p["url"] == url) and quoted(quote, p["raw_content"])
                     and (not identity or same_product(p))), None)

    if out.current_revision and not any(same_product(p) and revision_supported(out.current_revision, p["raw_content"]) for p in pages):
        out.current_revision = None
    family_name = re.sub(r"\s+(?:product\s+)?(?:family|series|range)$", "", (out.status_family or "").strip(), flags=re.I)
    notice = re.sub(r"[*`]", "", out.status_quote or "")
    predicate = (r"\s+(?:is|are|was|were|will\s+be|has\s+been|have\s+been)\s+"
                 r"(?:(?:now|being|fully|officially|permanently|currently)\s+)*"
                 r"(?:discontinued|obsolete|retired|no\s+longer\s+(?:made|manufactured|available))\b"
                 if out.status == "discontinued" else
                 r"\s+(?:is|are|remains?)\s+(?:(?:now|still|currently)\s+)*(?:active|available|made|manufactured|in\s+production)\b")
    family = (submitted and family_name and quoted(family_name, out.status_quote or "")
              and any(family_member(family_name, identifier) for identifier in (submitted.family, submitted.model) if identifier)
              and not re.search(r"\b(only|some|certain|except|excluding|optional|selected)\b", out.status_quote or "", re.I)
              and re.search(r"(?:^|[.!?,;])\s*(?:the\s+)?(?:(?:entire|whole)\s+)?" + re.escape(family_name)
                            + r"\s+(?:product\s+)?(?:family|series|range)\b" + predicate, notice, re.I))
    identifier = submitted.model or submitted.family or submitted.product if submitted else ""
    family_only = submitted and any(f and model_quoted(f, identifier) and model_quoted(identifier, f)
                                   for f in (submitted.family, family_name))
    model_status = submitted is None or (not family_only and model_quoted(identifier, out.status_quote or "")
                                        and re.search(r"(?<![\w+])" + re.escape(identifier) + predicate, notice, re.I))
    if out.status != "unknown" and not ((family or model_status) and source_of(out.status_quote, identity=not bool(family))):
        out.status = "unknown"
        out.status_quote = None
    read = len(out.current_values)
    out.current_values = [pv for pv in out.current_values if source_of(pv.quote, pv.source_url) and value_quoted(pv.value, pv.quote, pv.property)
                          and metric_quoted(pv.property, pv.quote) and unit_quoted(pv.unit, pv.quote)
                          and (submitted is None or pv.source_url and pv.model and pv.identity_quote)
                          and (not pv.identity_quote or source_of(pv.identity_quote, pv.source_url) == source_of(pv.quote, pv.source_url)
                               and (submitted is None or model_quoted(pv.model, pv.identity_quote)))
                          and (not pv.model or submitted is None or model_quoted(submitted.model or submitted.family or submitted.product, pv.model)
                               and model_quoted(pv.model, submitted.model or submitted.family or submitted.product))
                          and (not pv.variant or quoted(pv.variant, pv.quote or ""))]
    for pv in out.current_values:
        pv.selection_quote = None
        if submitted is not None:
            wide = (scope_is_product_wide(pv.scope, pv.scope_quote, pv.quote)
                    and source_of(pv.scope_quote, pv.source_url))
            if not pv.variant and not wide:
                pv.variant = pv.quote
            if pv.variant and submitted.selection and model_quoted(pv.variant, submitted.selection.model):
                pv.selection_quote = submitted.selection.quote
    if measure:
        metrics.count("web_values_read", "web_values_kept", read, len(out.current_values))
    confirmed = {pv.property: source_of(pv.quote, pv.source_url) for pv in out.current_values}
    return confirmed


def compare(submitted: ClaimsOut, out: VerifyOut, confirmed: dict, evidence: list[Evidence], pages: list[dict]
            ) -> tuple[list[Finding], list[CompareRow]]:
    """One comparison path for every accepted document; models supply quoted values only."""
    claims = _unambiguous(submitted.claims)
    rows: list[CompareRow] = []
    changed: list[CompareRow] = []
    for pv in _unambiguous(out.current_values).values():
        c = claims.get(pv.property)
        if c is None or not comparable_units(c.unit, pv.unit):
            continue
        row = CompareRow(
            property=pv.property,
            label=_label(pv.property),
            submitted=_fmt(c.value, c.unit),
            current=_fmt(pv.value, pv.unit),
            changed=not _same(c.value, pv.value, c.unit, pv.unit),
            source_url=confirmed[pv.property], quote=pv.quote,
        )
        rows.append(row)
        if row.changed:
            changed.append(row)

    newer = bool(out.current_revision and submitted.document_revision and out.current_revision != submitted.document_revision)
    if newer:
        rows.insert(0, CompareRow(property="document_revision", label=_label("document_revision"),
                                  submitted=submitted.document_revision, current=out.current_revision, changed=True))

    sent, now = submitted.document_revision or "undated", out.current_revision or "unknown"
    findings: list[Finding] = []
    if out.status == "discontinued":
        on = next((p["url"] for p in pages if quoted(out.status_quote, p["raw_content"])), None)
        findings.append(Finding(
            id="status-discontinued", check="status", verdict="fail", severity="major",
            title="Product is no longer made",
            detail=f"The manufacturer lists it as discontinued.{' Replacement: ' + out.replacement if out.replacement else ''}",
            compare=Compare(left_label="Status", right_label="Manufacturer", verdict="fail",
                            right_value=" ".join(x for x in ["Discontinued", out.status_date or ""] if x)),
            evidence=sorted(evidence, key=lambda e: e.url != on), quote=out.status_quote, decided_by="tavily + super",
        ))
    if changed:
        findings.append(Finding(
            id="currency-outdated", check="currency", verdict="outdated", severity="major",
            title="Data sheet is out of date",
            claim_ids=[claims[r.property].id for r in changed],
            compare=Compare(left_label=f"Submitted ({sent})", right_label=f"Current ({now})", verdict="changed", rows=changed),
            detail=f"The submitted sheet ({submitted.document_revision}) differs from the current one ({out.current_revision}) on: "
            + ", ".join(r.label for r in changed) + ".",
            evidence=evidence, decided_by="tavily + super",
        ))
    elif newer:
        findings.append(Finding(
            id="currency-newer", check="currency", verdict="note", severity="minor",
            title="Different revision found; no quoted values changed",
            detail=f"Submitted {submitted.document_revision}, web source {out.current_revision}. The revision labels differ; their age order is not confirmed.",
            compare=Compare(left_label="Submitted", left_value=sent, right_label="Current", right_value=now, verdict="changed"),
            evidence=evidence, decided_by="tavily + super",
        ))
    if not findings and not (out.current_revision or rows):  # nothing quoted from a source: can't call it current
        findings.append(Finding(
            id="currency-unverified", check="currency", verdict="unverified", severity="minor",
            title="Couldn't confirm the current documents",
            detail="No source quoted a revision or a value; check manually.", decided_by="tavily",
            compare=Compare(left_label="Submitted", left_value=sent, right_label="Current", right_value="Not found", verdict="fail"),
        ))
    if not findings:
        proof = []
        for e in evidence:
            quotes = [r.quote for r in rows if r.source_url == e.url and r.quote]
            if out.current_revision and any(p["url"] == e.url and revision_supported(out.current_revision, p["raw_content"])
                    and model_quoted(submitted.model or submitted.family or submitted.product, p["raw_content"]) for p in pages):
                quotes.append(out.current_revision)
            proof += [e.model_copy(update={"excerpt": quote}) for quote in dict.fromkeys(quotes)]
        findings.append(Finding(
            id="currency-current", check="currency", verdict="pass", severity="info",
            title="Data sheet matches the manufacturer's current version", evidence=proof, decided_by="tavily + super",
            compare=Compare(left_label="Submitted", left_value=sent, right_label="Current", right_value=now, verdict="pass"),
        ))
    if out.status == "active":
        status_evidence = [e.model_copy(update={"excerpt": out.status_quote}) for e in evidence
                           if any(p["url"] == e.url and quoted(out.status_quote, p["raw_content"]) for p in pages)]
        findings.append(Finding(id="status-active", check="status", verdict="pass", severity="info",
                                title="Product availability confirmed", quote=out.status_quote, evidence=status_evidence,
                                compare=Compare(left_label="Status", right_label="Manufacturer", right_value="Active", verdict="pass")))
    return findings, rows


def unconfirmed(reason: str) -> Finding:
    """A cap or provider failure leaves the web check unconfirmed."""
    return Finding(
        id="currency-unverified", check="currency", verdict="unverified", severity="minor",
        title="Couldn't confirm the current documents", detail=f"Web check skipped: {reason}. Check manually.",
        decided_by="code",
        compare=Compare(left_label="Submitted", right_label="Current", right_value="Not checked", verdict="fail"),
    )
