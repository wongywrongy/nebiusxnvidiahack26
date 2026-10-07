"""Step 7, send-backs only: find what the sub should send instead, and check it like a new submittal.

Status or currency problem: search for the maker's current sheet, or a current product in the same category.
Spec or listing problem: search for listed systems for the same penetrant and assembly.
Every candidate goes through the same extract -> spec_check -> verify as a submittal, so "passes" means
it clears the checks this item failed. At most settings.fix_max_candidates per finding, and the item's
Tavily credits for the fix stay under settings.fix_credit_cap.

Mock mode: data/fixtures/fix/<case>.json answers the search and extract, and fix/<case>-<n>.json
answers candidate n's claims and verify, shaped like a case fixture.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import ClaimsOut, Finding, Fix, FixCandidate, FixCheck, Requirement, Usage
from ..web import WebClient
from . import extract, spec_check, verify
from .decide import FLAGGED, decide

GROUPS = {"currency": ("status", "currency"), "spec": ("spec", "validity")}
VERIFY_CREDITS = 3  # verify's worst case: two basic searches and one extract
MAX_CANDIDATE_CHARS = 20000


async def find_fixes(case: dict, requirements: list[Requirement], claims: ClaimsOut, findings: list[Finding],
                     max_candidates: int, credit_cap: float) -> tuple[list[Usage], float]:
    """Attach a Fix to the worst flagged finding of each problem group. Returns usage and Tavily credits spent."""
    usage: list[Usage] = []
    credits = 0.0
    for group, checks in GROUPS.items():
        flagged = [f for f in findings if f.check in checks and f.verdict in FLAGGED and f.severity in ("critical", "major")]
        if not flagged:
            continue
        flagged.sort(key=lambda f: ("critical", "major").index(f.severity))
        fix, u, c = await _fix(case, group, flagged, requirements, claims, max_candidates, credit_cap - credits)
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


def _query(group: str, case: dict, claims: ClaimsOut, flagged: list[Finding]) -> str:
    maker = claims.manufacturer
    if group == "spec":
        where = case["title"].split(",", 1)[-1].strip()  # "steel pipe through gypsum wall"
        tail = " T rating equals F rating" if any(f.requirement_id == "fs-t-eq-f" for f in flagged) else ""
        return f"UL listed firestop system {_penetrant(case, claims)} {where}{tail}"
    if any(f.check == "status" for f in flagged):
        return f"{maker} current {_category(case)} data sheet"
    return f"{maker} {claims.product} {claims.model or ''} current data sheet".replace("  ", " ")


def _head(group: str, flagged: list[Finding], case: dict, claims: ClaimsOut, cands: list[FixCandidate]) -> str:
    ok = sum(c.passes for c in cands)
    if not cands:
        return "Nothing found online to suggest"
    if group == "spec":
        return f"Listed systems for {_penetrant(case, claims)}: {ok} of {len(cands)} pass"
    if any(f.check == "status" for f in flagged):
        return f"Current {_category(case)} found and checked" if ok else f"No current {_category(case)} found that passes"
    return "Current sheet found and re-checked" if ok else "No current sheet found that passes"


VERIFY_LABEL = {
    "status-discontinued": "Still made",
    "currency-current": "Current document",
    "currency-outdated": "Current document",
    "currency-newer": "Current document",
    "currency-unverified": "Current document",
}


def _row(f: Finding, reqs: dict[str, Requirement]) -> FixCheck:
    ok: Optional[bool] = {"pass": True, "note": True, "unverified": None}.get(f.verdict, False)
    r = reqs.get(f.requirement_id or "")
    right = f.compare.right_value if f.compare else None
    if f.verdict == "unverified":
        note = "not stated"
    elif f.id == "status-discontinued":
        note = "discontinued"
    elif isinstance(right, list):
        note = "" if ok else "not listed"
    else:
        note = "" if right in (None, "unknown") else str(right)
        if r and r.operator == "eq_ref":
            note = f"{spec_check.SHORT.get(r.property, '')} {note}".strip()  # "T 0 hr"
    label = r.text if r else VERIFY_LABEL.get(f.id, f.title)
    return FixCheck(label=label, ok=ok, note=note)


async def _fix(case: dict, group: str, flagged: list[Finding], requirements: list[Requirement], claims: ClaimsOut,
               max_candidates: int, cap: float) -> tuple[Fix, list[Usage], float]:
    fx = case.get("fixture", case["id"])
    fix_fx = f"fix/{fx}" if fx else None
    web = WebClient(fix_fx)
    own = {d.get("url") for d in case.get("submittal", [])}
    results = [r for r in await web.search(_query(group, case, claims, flagged)) if r["url"] not in own][:max_candidates]
    found = {p["url"]: p["raw_content"] for p in await web.extract([r["url"] for r in results])}

    roles = {d["role"] for d in case["submittal"]}
    props = sorted({r.property for r in requirements})
    reqs = {r.id: r for r in requirements}
    usage: list[Usage] = []
    verify_credits = 0.0
    cands: list[FixCandidate] = []
    for n, r in enumerate(results, start=1):
        text = found.get(r["url"])
        placeholder = bool(r.get("placeholder"))
        if not text:
            continue  # extract failed: nothing to check
        if not placeholder and web.credits + verify_credits + VERIFY_CREDITS > cap:
            break  # credit cap for this item
        cfx = f"{fix_fx}-{n}" if fix_fx else None
        pages = [{"page": 1, "text": text[:MAX_CANDIDATE_CHARS]}]
        cl, u = await extract.extract_claims(cfx, pages, extract.all_product_data(pages), props)
        usage.append(u)
        found_f = spec_check.check(requirements, cl.claims, roles)
        if not placeholder:  # a placeholder has no document online to verify
            vf, _, vu, vc = await verify.verify(
                {"id": cfx or case["id"], "fixture": cfx, "manufacturer_domains": case.get("manufacturer_domains", [])}, cl)
            found_f += vf
            usage += vu
            verify_credits += vc
        cands.append(FixCandidate(
            name=r.get("title") or cl.product, source_url=None if placeholder else r["url"], placeholder=placeholder,
            checks=[_row(f, reqs) for f in found_f if f.verdict != "not_applicable"],
            passes=decide(found_f) != "send_back",
        ))
    for u in usage:
        u.task = f"fix: {u.task}"
    best = next((c for c in cands if c.passes), None)
    fix = Fix(head=_head(group, flagged, case, claims, cands), candidates=cands, suggest=best.name if best else "")
    return fix, usage, web.credits + verify_credits
