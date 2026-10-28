"""Step 7, send-backs only: find what the sub should send instead, and check it like a new submittal.

Status or currency problem: search for the maker's current sheet, or a current product in the same category.
Spec or listing problem: search for listed systems for the same penetrant and assembly.
Every candidate goes through the same extract -> spec_check -> verify as a submittal. "Passes" only when
every check passed on quoted evidence; nothing unchecked is ever suggested. At most settings.fix_max_candidates per finding, and the item's
Tavily credits for the fix stay under settings.fix_credit_cap.

Mock mode: data/fixtures/fix/<case>.json answers the search and extract, and fix/<case>-<n>.json
answers candidate n's claims and verify, shaped like a case fixture.
"""

from __future__ import annotations

import json
from typing import Optional

from ..config import settings
from .. import archive
from ..llm import load_fixture
from ..providers import budget, tavily
from ..schemas import ClaimsOut, Evidence, Finding, Fix, FixCandidate, FixCheck, Investigation, Requirement, Usage
from ..web import WebClient, snapshot
from . import alternates, extract, spec_check, verify
from .decide import FLAGGED
from .investigate import investigate

GROUPS = {"currency": ("status", "currency"), "spec": ("spec", "validity")}


async def find_fixes(case: dict, requirements: list[Requirement], claims: ClaimsOut, findings: list[Finding],
                     max_candidates: int, credit_cap: float, *, investigations: list[Investigation] | None = None,
                     on_step=None, on_warning=None) -> tuple[list[Usage], float]:
    """Attach a Fix to the worst flagged finding of each problem group. Returns usage and Tavily credits spent."""
    usage: list[Usage] = []
    credits = 0.0
    for group, checks in GROUPS.items():
        flagged = [f for f in findings if f.check in checks and f.verdict in FLAGGED and f.severity in ("critical", "major")]
        if not flagged:
            continue
        flagged.sort(key=lambda f: ("critical", "major").index(f.severity))
        with budget.credit_scope(credit_cap - credits):
            fix, u, c = await _fix(case, group, flagged, requirements, claims, max_candidates, credit_cap - credits,
                                  investigations, on_step, on_warning)
        flagged[0].fix = fix
        usage += u
        credits += c
    return usage, credits


def _category(case: dict) -> str:
    return case["title"].split(",")[0].strip()  # "LED troffer, offices" -> "LED troffer"


def _penetrant(case: dict, claims: ClaimsOut) -> str:
    for c in case.get("conditions", []):
        if c["property"] == "penetrant_types":
            return str(c["value"])
    have = next((c.value for c in claims.claims if c.property == "penetrant_types"), None)
    return (have[0] if isinstance(have, list) and have else str(have or "")).split(" (")[0]


def _query(group: str, case: dict, claims: ClaimsOut, flagged: list[Finding], requirements: list[Requirement]) -> str:
    maker = claims.manufacturer
    if group == "spec":
        where = case["title"].split(",", 1)[-1].strip()  # "steel pipe through gypsum wall"
        ids = {f.requirement_id for f in flagged}
        if {r.section for r in requirements} != {"07 84 00"}:
            needed = "; ".join(f"{spec_check._label(r.property)} {spec_check._wanted(r)}" for r in requirements if r.id in ids)
            return f"{claims.product} manufacturer product data sheet {needed}"
        tail = "".join(f" {spec_check._label(r.property)} equals {spec_check._label(str(r.value))}"
                       for r in requirements if r.id in ids and r.operator == "eq_ref")
        return f"UL listed firestop system {_penetrant(case, claims)} {where}{tail}"
    if any(f.check == "status" for f in flagged):
        return f'"{_category(case)}" manufacturer specification sheet'
    return f"{maker} {claims.product} {claims.model or ''} current data sheet".replace("  ", " ")


def _head(group: str, flagged: list[Finding], case: dict, claims: ClaimsOut, cands: list[FixCandidate]) -> str:
    ok = sum(c.passes for c in cands)
    if not ok:
        return "No passing replacement found"
    if group == "spec":
        return (f"Listed systems for {_penetrant(case, claims)}: {ok} of {len(cands)} pass" if case.get("section") == "07 84 00"
                else f"Checked replacements: {ok} of {len(cands)} pass")
    if any(f.check == "status" for f in flagged):
        return f"Current {_category(case)} found and checked"
    return "Current sheet found and re-checked"


VERIFY_LABEL = {
    "status-discontinued": "Still made",
    "currency-current": "Current document",
    "currency-outdated": "Current document",
    "currency-newer": "Current document",
    "currency-unverified": "Current document",
}


def _row(f: Finding, reqs: dict[str, Requirement]) -> FixCheck:
    ok: Optional[bool] = {"pass": True, "note": None, "unverified": None, "pending": None}.get(f.verdict, False)
    r = reqs.get(f.requirement_id or "")
    right = f.compare.right_value if f.compare else None
    if f.verdict in ("unverified", "pending"):
        note = "not confirmed"
    elif f.id == "status-discontinued":
        note = "discontinued"
    elif isinstance(right, list):
        note = "" if ok else "not listed"
    else:
        note = "" if right in (None, "unknown") else str(right)
        if r and r.operator == "eq_ref":
            note = f"{spec_check.SHORT.get(r.property, '')} {note}".strip()  # "T 0 hr"
    label = spec_check._label(r.property) if r else VERIFY_LABEL.get(f.id, f.title)
    return FixCheck(label=label, check=f.check, ok=ok, note=note, requirement_id=f.requirement_id,
                    claim_ids=f.claim_ids, evidence=f.evidence)


async def _fix(case: dict, group: str, flagged: list[Finding], requirements: list[Requirement], claims: ClaimsOut,
               max_candidates: int, cap: float, investigations=None, on_step=None, on_warning=None) -> tuple[Fix, list[Usage], float]:
    fx = case.get("fixture", case["id"])
    fix_fx = f"fix/{fx}" if fx else None
    web = WebClient(fix_fx, on_step, on_warning)
    own = {d.get("url") for d in case.get("submittal", [])}
    query = _query(group, case, claims, flagged, requirements)
    domains = case.get("manufacturer_domains", []) if group == "currency" and not any(f.check == "status" for f in flagged) else []
    results = await web.search(query, include_domains=domains or None)
    known = [{"url": row.source_url, "title": next((e.title for e in f.evidence if e.url == row.source_url), row.source_url)}
             for f in flagged if f.check == "currency" and f.compare for row in f.compare.rows
             if row.changed and row.source_url and row.quote]
    by_url = {}
    for result in [*known, *results]:
        if result["url"] not in own:
            by_url.setdefault(result["url"], result)
    results = list(by_url.values())[:max_candidates]
    found = {p.get("requested_url", p["url"]): p for p in await web.extract([r["url"] for r in results])}

    roles = {d["role"] for d in case["submittal"]}
    props = spec_check.properties_for(requirements)
    reqs = {r.id: r for r in requirements}
    usage: list[Usage] = []
    verify_credits = 0.0
    cands: list[FixCandidate] = []
    for n, r in enumerate(results, start=1):
        page = found.get(r["url"])
        text = page["raw_content"] if page else None
        if page:
            r = {**r, "url": page["url"]}
        cfx = f"{fix_fx}-{n}" if fix_fx else None
        if not text:
            if not settings.live and (not cfx or not (settings.fixtures_dir / f"{cfx}.json").exists()
                                      or not load_fixture(cfx).get("investigate")):
                continue
            candidate = ClaimsOut(product=r.get("title") or claims.product, manufacturer=claims.manufacturer, claims=[])
            candidate_web = WebClient(cfx, on_step, on_warning)
            inv = await investigate({**case, "candidate_url": r["url"]}, candidate, candidate_web)
            inv.purpose = "replacement"
            usage += inv._usage
            verify_credits += candidate_web.credits
            if investigations is not None:
                investigations.append(inv)
            page = next((p for p in inv._pages if p["url"] == inv._document_url), None)
            if not page:
                continue
            text = page["raw_content"]
            r = {"url": page["url"], "title": inv._document_title}
        scripted_cost = (4 if case.get("manufacturer_domains") else 3) * tavily.search_credits(settings.search_depth)
        scripted_cost += 2 * tavily.extract_credits(3, settings.extract_depth)
        if web.credits + verify_credits + scripted_cost > cap:
            await web.warn("fix", budget.BudgetExceeded("Fix credit cap reached before candidate verification"))
            break  # credit cap for this item
        pages = page.get("pages") or [{"page": 1, "text": text}]
        proposal_options = {"propose": True} if settings.live else {}
        cl, u = await extract.extract_claims(cfx, pages, extract.all_product_data(pages), props, **proposal_options)
        usage += u
        if not verify._unambiguous(cl.claims):
            continue  # no quoted product properties: cannot establish a passing replacement
        sources, verification = [], []
        candidate_domains = (case.get("manufacturer_domains", []) if
                             spec_check._text(cl.manufacturer) == spec_check._text(claims.manufacturer) else [])
        vf, _, vu, vc, inv = await verify.verify(
            {"id": cfx or case["id"], "fixture": cfx, "manufacturer_domains": candidate_domains,
             "candidate_url": r["url"], "require_availability": True,
             "required_properties": sorted({r.property for r in requirements if not r.applies_to or roles.intersection(r.applies_to)} |
                                           {str(r.value) for r in requirements if r.operator == "eq_ref" and
                                            (not r.applies_to or roles.intersection(r.applies_to))})}, cl,
            on_step=on_step, on_warning=on_warning, on_sources=sources.extend, on_proof=verification.append)
        if inv is not None and investigations is not None:
            inv.purpose = "replacement"
            investigations.append(inv)
        usage += vu
        verify_credits += vc
        bundle = [page]
        proof_urls = {e.url for f in vf for e in f.evidence}
        for source in sorted(sources, key=lambda p: p["url"] not in proof_urls):
            if source["url"] not in {p["url"] for p in bundle} and len(bundle) < 3 and extract.model_quoted(
                    cl.model or cl.product, source["raw_content"]):
                bundle.append(source)
        documents, bundle_pages, page_sources = [], [], {}
        for source in bundle:
            document = Evidence(tier=verify.classify(source["url"], case.get("manufacturer_domains", [])),
                                title=source["url"], **{**snapshot(source["url"], source["raw_content"], source.get("retrieved_at")),
                                    **{key:source[key] for key in ("sha256", "retrieved_at", "archived_path", "cache_hit") if key in source}})
            documents.append(document)
            for p in source.get("pages") or [{"page": 1, "text": source["raw_content"]}]:
                number = p["page"] if source is page else max(page_sources, default=0) + 1
                bundle_pages.append({**p, "page": number})
                page_sources[number] = document
                if p["text"] != source["raw_content"]:
                    page_sources[number] = document.model_copy(update={
                        **snapshot(document.url, p["text"], document.retrieved_at),
                        "archived_path": archive.save(case["id"], p["text"].encode(), "txt", document.retrieved_at),
                    })
        if len(bundle) > 1:
            more, u = await extract.extract_claims(cfx, bundle_pages, extract.all_product_data(bundle_pages), props, **proposal_options)
            identifier, other = cl.model or cl.family or cl.product, more.model or more.family or more.product
            selection_agrees = (not cl.selection or more.selection and
                                extract.model_quoted(cl.selection.model, more.selection.model) and
                                extract.model_quoted(more.selection.model, cl.selection.model)
                                and cl.selection.origin == more.selection.origin)
            if selection_agrees and extract.model_quoted(identifier, other) and extract.model_quoted(other, identifier):
                for claim in more.claims:
                    claim.selection_quote = (cl.selection.quote if claim.variant and cl.selection and
                                             extract.selection_matches(cl.selection, claim.variant) else None)
                merged, identifiers = {}, set()
                for claim in [*cl.claims, *more.claims]:
                    key = (claim.property, json.dumps(claim.value, sort_keys=True), claim.unit,
                           claim.variant, claim.selection_quote)
                    if key in merged:
                        continue
                    while claim.id in identifiers:
                        claim = claim.model_copy(update={"id": claim.id + "-bundle"})
                    identifiers.add(claim.id)
                    merged[key] = claim
                cl = cl.model_copy(update={"claims": list(merged.values())})
            usage += u
        found_f = spec_check.check(requirements, cl.claims, roles)
        by_id = {c.id: c for c in cl.claims}
        for finding in found_f:
            finding.evidence = [page_sources[c.page].model_copy(update={"excerpt": c.quote})
                                for cid in finding.claim_ids if (c := by_id.get(cid)) and c.page in page_sources]
        by_url = {d.url: d for d in documents}
        for finding in vf:
            finding.evidence = [e for e in finding.evidence if e.url in by_url]
        found_f += vf
        checks = [_row(f, reqs) for f in found_f if f.verdict != "not_applicable"]
        checked = {f.requirement_id for f in found_f if f.verdict != "not_applicable"}
        for original in flagged:
            if original.requirement_id in reqs and original.requirement_id not in checked:
                req = reqs[original.requirement_id]
                checks.append(FixCheck(label=spec_check._label(req.property), ok=None,
                                       check=req.check, requirement_id=req.id,
                                       note="No quoted evidence that this corrects the failed requirement"))
            elif original.requirement_id:
                for check in checks:
                    if check.requirement_id == original.requirement_id and check.ok is None:
                        check.note = "No quoted evidence that this corrects the failed requirement"
        if not any(f.id == "status-active" and f.evidence for f in vf):
            checks.append(FixCheck(label="Still made", check="status", ok=None,
                                   note="No quoted confirmation that this replacement is available"))
        cands.append(FixCandidate(
            name=r.get("title") or cl.product, source_url=r["url"], documents=documents, checks=checks,
            claims=cl.claims, selection=cl.selection, document_roles=sorted(roles),
            extracted=cl, verification=verification[0] if verification else None, page_sources=page_sources,
            passes=bool(checks) and all(k.ok is True and k.evidence for k in checks),
        ))
    for u in usage:
        if u.task != "investigate":
            u.task = f"fix: {u.task}"
    best = next((c for c in cands if c.passes), None)
    suggestion = (f"SpecCheck proposal: {best.selection.model}. Confirm configuration before ordering."
                  if best and best.selection and best.selection.origin == "agent_proposal" else best.name if best else "")
    origins = {k["url"]: "current_document" for k in known}
    fix = Fix(head=_head(group, flagged, case, claims, cands), query=query, candidates=cands, suggest=suggestion,
              alternates=alternates.rank(cands, requirements, claims.claims, origins))
    return fix, usage, web.credits + verify_credits
