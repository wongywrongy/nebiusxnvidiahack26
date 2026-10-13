"""Step 4b: check the submittal against the live web.

For one product: find the manufacturer's current document and product status with Tavily,
let Nemotron Super read what came back, then diff the values in plain code.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from ..config import settings
from ..llm import load_fixture, router
from ..providers import ProviderError, budget
from ..schemas import ClaimsOut, Compare, CompareRow, Evidence, Finding, Investigation, Usage, VerifyOut
from ..web import WebClient, snapshot
from .extract import quoted
from .investigate import investigate
from .spec_check import _fmt, _label, to_number

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


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return sorted(map(str, a or [])) == sorted(map(str, b or []))
    na, nb = to_number(a), to_number(b)
    if na is not None and nb is not None and str(a).strip()[:1] not in "<>" and str(b).strip()[:1] not in "<>":
        return abs(na - nb) < 1e-9
    return str(a).strip().lower() == str(b).strip().lower()


async def verify(case: dict, submitted: ClaimsOut, *, on_step=None
                 ) -> tuple[list[Finding], list[CompareRow], list[Usage], float, Investigation | None]:
    fx = case.get("fixture", case["id"])  # uploads: the matching case's fixture, or None
    web = WebClient(fx, on_step)
    domains = case.get("manufacturer_domains", [])
    name = " ".join(x for x in [submitted.manufacturer, submitted.product, submitted.model or ""] if x)

    # 1. Search: current document, and product status.
    results = await web.search(f"{name} data sheet", include_domains=domains or None, include_domains_mode="prefer")
    model = (submitted.model or "").replace('"', '').strip()
    status_name = " ".join(x for x in [submitted.manufacturer, submitted.product, f'"{model}"' if model else ""] if x)
    results += await web.search(f"{status_name} discontinued OR replaced", topic="news",
                                include_published_date=True, exact_match=bool(model))
    # One bounded map attempt can find a PDF missed by search before escalating to the investigator.
    if domains and not any(classify(r["url"], domains) == "manufacturer" for r in results):
        try:
            with budget.credit_scope(5):  # at most 4 for an instructed map + 1 for extracting three URLs
                links = await web.map(f"https://{domains[0]}", instructions=f"Find the current PDF data sheet for {name}",
                                      limit=20, max_depth=1)
                links = sorted(dict.fromkeys(links), key=lambda url: not urlparse(url).path.lower().endswith(".pdf"))[:3]
                mapped = await web.extract(links)
        except (budget.BudgetExceeded, ProviderError):
            mapped = []  # keep the search evidence; an unsuccessful optional lookup cannot erase it
    else:
        mapped = []
    seen, ranked = set(), []
    for r in sorted(results, key=lambda r: TIER_RANK[classify(r["url"], domains)]):
        if r["url"] not in seen:
            seen.add(r["url"])
            ranked.append(r)

    # 2. Extract the best few pages.
    pages = await web.extract([r["url"] for r in ranked[:3]])
    pages += [p for p in mapped if p["url"] not in {p["url"] for p in pages}]
    titles = {r["url"]: r.get("title", "") for r in ranked}

    # 3. Super reads the sources; the quote gate runs before the investigator trigger.
    out, u = await read_sources(fx, submitted, pages)
    usage = [u]
    confirmed = gate(out, pages)
    investigation = None
    # A quoted revision or discontinuation already answered the scripted check.
    if (settings.live or load_fixture(fx).get("investigate")) and out.current_revision is None and out.status != "discontinued" and (
        not out.current_values or (out.status == "unknown" and
                                  not any(classify(r["url"], domains) == "manufacturer" for r in ranked))
    ):
        investigation = await investigate(case, submitted, web)
        usage += investigation._usage
        if investigation.outcome == "found":
            accepted = [p for p in investigation._pages if p["url"] == investigation._document_url]
            newer = investigation._verified.model_copy(deep=True)
            try:
                newer, u = await read_sources(fx, submitted, accepted, investigated=True)
                usage.append(u)
            except (budget.BudgetExceeded, ProviderError):
                pass  # the loop's verified quotes still stand if the value read cannot run
            gate(newer, accepted)
            newer.current_revision = newer.current_revision or investigation._verified.current_revision
            if investigation._verified.status != "unknown":
                newer.status = investigation._verified.status
                newer.status_quote = investigation._verified.status_quote
            out = newer
            pages += investigation._pages
            titles[investigation._document_url] = investigation._document_title
            confirmed = gate(out, pages)

    evidence = [
        Evidence(tier=classify(p["url"], domains), title=titles.get(p["url"], p["url"]), **snapshot(p["url"], p["raw_content"]))
        for p in pages
    ]
    findings, rows = compare(submitted, out, confirmed, evidence, pages)
    return findings, rows, usage, web.credits, investigation


async def read_sources(fx, submitted: ClaimsOut, pages: list[dict], investigated=False) -> tuple[VerifyOut, Usage]:
    submitted_view = {
        "product": submitted.product,
        "manufacturer": submitted.manufacturer,
        "model": submitted.model,
        "document_revision": submitted.document_revision,
        "claims": [{"property": c.property, "value": c.value, "unit": c.unit} for c in submitted.claims],
    }
    sources = [{"url": p["url"], "text": p["raw_content"][:12000]} for p in pages]
    return await router.call(
        "verify",
        VerifyOut,
        [
            {
                "role": "user",
                "content": (
                    "Compare the submitted product data with these current web sources. "
                    "Report product status, the current document revision exactly as printed, and the CURRENT value for each "
                    "submitted property you can find, each with the exact quote from the source that states it. "
                    "Use the same property names. Only use values stated in the sources.\n\n"
                    f"SUBMITTED:\n{json.dumps(submitted_view)}\n\nSOURCES:\n{json.dumps(sources)}"
                ),
            }
        ],
        {"case_id": fx, "fixture_key": "investigate_verify" if investigated else "verify"},
    )


def gate(out: VerifyOut, pages: list[dict]) -> dict[str, str]:
    """Keep only what a fetched page actually quotes, for both scripted and investigated sources."""
    def source_of(quote):
        return next((p["url"] for p in pages if quoted(quote, p["raw_content"])), None)

    if out.current_revision and not source_of(out.current_revision):
        out.current_revision = None
    if out.status != "unknown" and not source_of(out.status_quote):
        out.status = "unknown"
        out.status_quote = None
    out.current_values = [pv for pv in out.current_values if source_of(pv.quote)]
    confirmed = {pv.property: source_of(pv.quote) for pv in out.current_values}
    return confirmed


def compare(submitted: ClaimsOut, out: VerifyOut, confirmed: dict, evidence: list[Evidence], pages: list[dict]
            ) -> tuple[list[Finding], list[CompareRow]]:
    """One comparison path for every accepted document; models supply quoted values only."""
    claims = {c.property: c for c in submitted.claims}
    rows: list[CompareRow] = []
    changed: list[CompareRow] = []
    for pv in out.current_values:
        c = claims.get(pv.property)
        if c is None:
            continue
        row = CompareRow(
            property=pv.property,
            label=_label(pv.property),
            submitted=_fmt(c.value, c.unit),
            current=_fmt(pv.value, pv.unit),
            changed=not _same(c.value, pv.value),
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
            title="A newer data sheet exists; no values changed",
            detail=f"Submitted {submitted.document_revision}, current {out.current_revision}. Ask for the current sheet for the record.",
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
        findings.append(Finding(
            id="currency-current", check="currency", verdict="pass", severity="info",
            title="Data sheet matches the manufacturer's current version", evidence=evidence, decided_by="tavily + super",
            compare=Compare(left_label="Submitted", left_value=sent, right_label="Current", right_value=now, verdict="pass"),
        ))
    return findings, rows


def unconfirmed(reason: str) -> Finding:
    """A cap or provider failure leaves the web check unconfirmed."""
    return Finding(
        id="currency-unverified", check="currency", verdict="unverified", severity="minor",
        title="Couldn't confirm the current documents", detail=f"Web check skipped: {reason}. Check manually.",
        decided_by="code",
        compare=Compare(left_label="Submitted", right_label="Current", right_value="Not checked", verdict="fail"),
    )
