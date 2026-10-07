"""Step 4b: check the submittal against the live web.

For one product: find the manufacturer's current document and product status with Tavily,
let Nemotron Super read what came back, then diff the values in plain code.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from ..llm import router
from ..schemas import ClaimsOut, Compare, CompareRow, Evidence, Finding, Usage, VerifyOut
from ..web import WebClient, snapshot
from .extract import quoted

LISTING_BODIES = ("ul.com", "intertek.com", "icc-es.org", "designlights.org", "energystar.gov")
TIER_RANK = {"manufacturer": 0, "listing_body": 1, "distributor": 2, "agency": 3, "archive": 4, "other": 5}

LABELS = {
    "f_rating_hr": "Fire rating (F)",
    "t_rating_hr": "Temperature rating (T)",
    "voc_g_per_l": "VOC (air quality)",
    "max_annular_space_in": "Largest gap it can seal",
    "service_temp_max_f": "Highest service temperature",
    "service_temp_range_f": "Service temperature range",
    "lumens": "Light output",
    "watts": "Power draw",
    "efficacy_lm_per_w": "Efficiency (lumens per watt)",
    "cri": "Color quality (CRI)",
    "warranty_years": "Warranty",
    "l70_hours": "Rated life (L70)",
    "dim_min_percent": "Dims down to",
    "input_watts_120v": "Power at 120 V",
    "input_watts_277v": "Power at 277 V",
    "standards": "Test standards",
    "dlc_listed": "DLC listing",
    "penetrant_types": "Pipe types covered",
    "document_revision": "Data sheet version",
}


def classify(url: str, manufacturer_domains: list[str]) -> str:
    host = urlparse(url).netloc.lower()
    if any(host.endswith(d) for d in manufacturer_domains):
        return "manufacturer"
    if "web.archive.org" in host:
        return "archive"
    if any(host.endswith(d) for d in LISTING_BODIES):
        return "listing_body"
    if host.endswith(".gov") or host.endswith(".edu"):
        return "agency"
    return "distributor"


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return sorted(map(str, a or [])) == sorted(map(str, b or []))
    from .spec_check import to_number

    na, nb = to_number(a), to_number(b)
    if na is not None and nb is not None and str(a).strip()[:1] not in "<>" and str(b).strip()[:1] not in "<>":
        return abs(na - nb) < 1e-9
    return str(a).strip().lower() == str(b).strip().lower()


async def verify(case: dict, submitted: ClaimsOut) -> tuple[list[Finding], list[CompareRow], list[Usage], float]:
    fx = case.get("fixture", case["id"])  # uploads: the matching case's fixture, or None
    web = WebClient(fx)
    domains = case.get("manufacturer_domains", [])
    name = " ".join(x for x in [submitted.manufacturer, submitted.product, submitted.model or ""] if x)

    # 1. Search: current document, and product status.
    results = await web.search(f"{name} data sheet", include_domains=domains or None)
    results += await web.search(f"{name} discontinued OR replaced")
    seen, ranked = set(), []
    for r in sorted(results, key=lambda r: TIER_RANK[classify(r["url"], domains)]):
        if r["url"] not in seen:
            seen.add(r["url"])
            ranked.append(r)

    # 2. Extract the best few pages.
    pages = await web.extract([r["url"] for r in ranked[:3]])
    titles = {r["url"]: r.get("title", "") for r in ranked}

    # 3. Super reads the sources against the submitted claims.
    submitted_view = {
        "product": submitted.product,
        "manufacturer": submitted.manufacturer,
        "model": submitted.model,
        "document_revision": submitted.document_revision,
        "claims": [{"property": c.property, "value": c.value, "unit": c.unit} for c in submitted.claims],
    }
    sources = [{"url": p["url"], "text": p["raw_content"][:12000]} for p in pages]
    out, usage = await router.call(
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
        {"case_id": fx},
    )

    evidence = [
        Evidence(tier=classify(p["url"], domains), title=titles.get(p["url"], p["url"]), **snapshot(p["url"], p["raw_content"]))
        for p in pages
    ]

    # 4. Keep only what the sources actually say: every value, revision and status needs a quote found on a fetched page.
    def source_of(quote):
        return next((p["url"] for p in pages if quoted(quote, p["raw_content"])), None)

    if out.current_revision and not source_of(out.current_revision):
        out.current_revision = None
    if out.status == "discontinued" and not source_of(out.status_quote):
        out.status = "unknown"
    confirmed = {pv.property: url for pv in out.current_values if (url := source_of(pv.quote))}
    out.current_values = [pv for pv in out.current_values if pv.property in confirmed]

    # 5. Diff in code.
    claims = {c.property: c for c in submitted.claims}
    rows: list[CompareRow] = []
    changed: list[CompareRow] = []
    for pv in out.current_values:
        c = claims.get(pv.property)
        if c is None:
            continue
        row = CompareRow(
            property=pv.property,
            label=LABELS.get(pv.property, pv.property.replace("_", " ")),
            submitted=_show(c.value, c.unit),
            current=_show(pv.value, pv.unit),
            changed=not _same(c.value, pv.value),
            source_url=confirmed[pv.property], quote=pv.quote,
        )
        rows.append(row)
        if row.changed:
            changed.append(row)

    newer = bool(out.current_revision and submitted.document_revision and out.current_revision != submitted.document_revision)
    if newer:
        rows.insert(0, CompareRow(property="document_revision", label=LABELS["document_revision"],
                                  submitted=submitted.document_revision, current=out.current_revision, changed=True))

    sent, now = submitted.document_revision or "undated", out.current_revision or "unknown"
    findings: list[Finding] = []
    if out.status == "discontinued":
        findings.append(Finding(
            id="status-discontinued", check="status", verdict="fail", severity="major",
            title="Product is no longer made",
            detail=f"The manufacturer lists it as discontinued.{' Replacement: ' + out.replacement if out.replacement else ''}",
            compare=Compare(left_label="Status", right_label="Manufacturer", verdict="fail",
                            right_value=" ".join(x for x in ["Discontinued", out.status_date or ""] if x)),
            evidence=evidence, decided_by="tavily + super",
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
    return findings, rows, [usage], web.credits


def _show(value, unit) -> str:
    from .spec_check import _fmt

    return _fmt(value, unit)
