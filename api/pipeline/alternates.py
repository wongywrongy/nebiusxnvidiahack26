"""Rank checked fix candidates into "what to send instead", in code.

Every candidate has already been through extract -> spec check -> verify in fix.py. This module only sorts and
labels what those checks found, so a reviewer sees the best option first and exactly what is still unproven:

- meets_spec: every check passed on quoted evidence (the same bar as FixCandidate.passes).
- possible:   nothing failed, but some checks are unconfirmed; `confirm` lists them.
- failed:     at least one check failed; `failed` lists them.

"Better" marks compare the candidate's quoted value with the submitted value for each numeric requirement, in
the requirement's direction (gte: higher is better, lte: lower is better). Nothing here calls a model, and
nothing is called "equivalent" unless it meets the spec.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import Alternate, BetterMark, Claim, FixCandidate, Requirement
from .spec_check import _fmt, _label, meets, normalize

RANK_ORDER = {"meets_spec": 0, "possible": 1, "failed": 2}


def _numeric(claims: list[Claim], prop: str) -> Optional[Claim]:
    """The single product-wide (or selected) quoted value for a property, else None."""
    usable = [c for c in claims if c.property == prop and (not c.variant or c.selection_quote)]
    return usable[0] if len(usable) == 1 else None


def better_marks(candidate: FixCandidate, requirements: list[Requirement], submitted: list[Claim]) -> list[BetterMark]:
    marks: list[BetterMark] = []
    for r in requirements:
        if r.operator not in ("gte", "lte"):
            continue
        alt = _numeric(candidate.claims, r.property)
        if alt is None:
            continue
        sub = _numeric(submitted, r.property)
        alt_ok = meets(r, alt)
        a = normalize(alt.value, alt.unit or r.unit)
        s = normalize(sub.value, sub.unit or r.unit) if sub else None
        if alt_ok is not True:
            mark = "worse" if alt_ok is False else "unknown"
        elif a is None or s is None:
            mark = "meets"
        elif (a > s if r.operator == "gte" else a < s):
            mark = "better"
        elif a == s:
            mark = "meets"
        else:
            mark = "worse"  # meets the spec but is weaker than what was submitted
        marks.append(BetterMark(requirement_id=r.id, label=_label(r.property), mark=mark,
                                alternate=_fmt(alt.value, alt.unit),
                                submitted=_fmt(sub.value, sub.unit) if sub else None))
    return marks


def rank_one(candidate: FixCandidate, requirements: list[Requirement], submitted: list[Claim],
             origin: str = "search") -> Alternate:
    failed = [k.label for k in candidate.checks if k.ok is False]
    unconfirmed = [k.label for k in candidate.checks if k.ok is None or (k.ok is True and not k.evidence)]
    if candidate.passes and not failed:
        rank = "meets_spec"
    elif not failed and candidate.checks:
        rank = "possible"
    else:
        rank = "failed"
    return Alternate(name=candidate.name, source_url=candidate.source_url, rank=rank,
                     confirm=list(dict.fromkeys(unconfirmed)) if rank == "possible" else [],
                     failed=list(dict.fromkeys(failed)) if rank == "failed" else [],
                     better=better_marks(candidate, requirements, submitted), origin=origin)


def rank(candidates: list[FixCandidate], requirements: list[Requirement], submitted: list[Claim],
         origins: Optional[dict[str, str]] = None) -> list[Alternate]:
    """Best first: meets_spec, then possible (fewest things to confirm, most 'better' marks), then failed."""
    origins = origins or {}
    ranked = [rank_one(c, requirements, submitted, origins.get(c.source_url, "search")) for c in candidates]
    return sorted(ranked, key=lambda a: (RANK_ORDER[a.rank], len(a.confirm) + len(a.failed),
                                         -sum(m.mark == "better" for m in a.better)))
