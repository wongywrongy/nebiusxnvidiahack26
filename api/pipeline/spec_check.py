"""Step 4a: compare claims to requirements in plain code. No model, no guessing."""

from __future__ import annotations

import re
from typing import Optional

from ..schemas import Claim, Compare, Finding, Requirement

UNIT_TO_BASE = {
    # length -> inches
    "in": ("in", 1.0), "inch": ("in", 1.0), "inches": ("in", 1.0), "mm": ("in", 1 / 25.4), "cm": ("in", 1 / 2.54),
    # time -> hours
    "hr": ("hr", 1.0), "h": ("hr", 1.0), "hour": ("hr", 1.0), "hours": ("hr", 1.0), "min": ("hr", 1 / 60),
    "yr": ("yr", 1.0), "years": ("yr", 1.0), "year": ("yr", 1.0),
}


def to_number(value) -> Optional[float]:
    """Parse 2, '2', '3/4', '1-1/8', '<2', '1/2 hr' into a float. None if not numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    s = value.strip().lower().lstrip("<>~≤≥= ")
    m = re.match(r"^(\d+)[-\s](\d+)/(\d+)", s)
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.match(r"^(\d+)/(\d+)", s)
    if m:
        return int(m.group(1)) / int(m.group(2))
    m = re.match(r"^-?\d+(\.\d+)?", s.replace(",", ""))
    return float(m.group(0)) if m else None


def normalize(value, unit: Optional[str]) -> Optional[float]:
    n = to_number(value)
    if n is None:
        return None
    if unit and unit.lower() in UNIT_TO_BASE:
        return n * UNIT_TO_BASE[unit.lower()][1]
    return n


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).lower() for v in value]
    return [str(value).lower()]


OPERATOR_WORDS = {"gte": "at least", "lte": "at most", "eq": "exactly"}


def _label(prop: str) -> str:
    from .verify import LABELS  # plain-language names live with the comparison table

    return LABELS.get(prop, prop.replace("_", " "))


def _fmt(value, unit) -> str:
    if isinstance(value, list):
        return ", ".join(map(str, value))
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value} {unit}".strip() if unit else str(value)


SYMBOL = {"gte": "≥", "lte": "≤", "eq": "="}
SHORT = {"t_rating_hr": "T", "f_rating_hr": "F"}


def _wanted(r: Requirement):
    """What the requirement asks for, in the form the comparison shows it."""
    if r.operator in SYMBOL:
        return f"{SYMBOL[r.operator]} {_fmt(r.value, r.unit)}"
    if r.operator == "eq_ref":
        return f"{SHORT.get(r.property, _label(r.property))} = {SHORT.get(str(r.value), _label(str(r.value)))}"
    if r.operator == "contains":
        return [str(r.value)]
    if r.operator == "any_of":
        return list(r.value) if isinstance(r.value, list) else [str(r.value)]
    return r.text


def check(requirements: list[Requirement], claims: list[Claim], roles: Optional[set[str]] = None) -> list[Finding]:
    """roles: the submittal's document roles; a requirement whose applies_to misses them all is not applicable."""
    by_prop: dict[str, list[Claim]] = {}
    for c in claims:
        by_prop.setdefault(c.property, []).append(c)

    findings: list[Finding] = []
    for r in requirements:
        found = by_prop.get(r.property, [])
        claim = found[0] if found else None
        ref = f"{r.section} {r.paragraph}".strip()
        related: list[str] = []  # other claims the comparison used (eq_ref)
        left_label, right_label = ("Job needs", "Listing covers") if r.check == "validity" else ("Spec requires", "Submitted")

        def make(verdict: str, title: str, detail: str = "", severity: Optional[str] = None,
                 left=None, right=None) -> Finding:
            shown = right if right is not None else (claim.value if isinstance(claim.value, list) else _fmt(claim.value, claim.unit)) if claim else "Not stated"
            return Finding(
                id=f"{r.check}-{r.id}",
                check=r.check,
                verdict=verdict,
                severity="info" if verdict in ("pass", "not_applicable") else (severity or r.severity),
                title=title,
                detail=detail,
                requirement_id=r.id,
                claim_id=claim.id if claim else None,
                claim_ids=[claim.id, *related] if claim else [],
                spec_ref=ref,
                compare=Compare(left_label=left_label, left_value=left if left is not None else _wanted(r),
                                right_label=right_label, right_value=shown, verdict="pass" if verdict == "pass" else "fail"),
            )

        if r.applies_to and roles and not set(r.applies_to) & roles:
            findings.append(make("not_applicable", _label(r.property), f"Applies to {', '.join(r.applies_to)} only."))
            continue

        if r.operator == "exists":
            findings.append(make("pass", _label(r.property), right="Included") if found
                            else make("fail", f"Missing: {_label(r.property)}", "Not found in the package.", right="Not found"))
            continue

        if r.operator == "eq_ref" and (claim is None or not by_prop.get(str(r.value))):
            continue  # rule only applies when both values are present (e.g. T = F applies to systems, not sealant sheets)

        if claim is None:
            findings.append(make("unverified", f"Not stated: {_label(r.property)}", r.text, severity="minor"))
            continue

        ok: Optional[bool] = None
        detail = ""
        left = None
        if r.operator in ("gte", "lte", "eq"):
            a, b = normalize(claim.value, claim.unit), normalize(r.value, r.unit)
            if a is not None and b is not None:
                ok = {"gte": a >= b, "lte": a <= b, "eq": abs(a - b) < 1e-9}[r.operator]
                detail = f"Package states {_fmt(claim.value, claim.unit)}; spec requires {OPERATOR_WORDS[r.operator]} {_fmt(r.value, r.unit)}."
        elif r.operator == "eq_ref":
            other = by_prop.get(str(r.value), [])
            if other:
                related = [other[0].id]
                a, b = normalize(claim.value, claim.unit), normalize(other[0].value, other[0].unit)
                if a is not None and b is not None:
                    ok = abs(a - b) < 1e-9
                    left = f"{_wanted(r)} ({_fmt(other[0].value, other[0].unit)})"  # "T = F (2 hr)"
                    detail = (f"{_label(r.property)} is {_fmt(claim.value, claim.unit)} but "
                              f"{_label(str(r.value))} is {_fmt(other[0].value, other[0].unit)}.")
        elif r.operator == "contains":
            have = _as_list(claim.value)
            want = str(r.value).lower()
            ok = any(want in h for h in have)
            detail = f"Package lists {_fmt(claim.value, None)}; needs {r.value}."
        elif r.operator == "any_of":
            allowed = _as_list(r.value)
            ok = any(h in allowed for h in _as_list(claim.value))
            detail = f"Package states {_fmt(claim.value, None)}; allowed: {_fmt(r.value, None)}."

        if ok is None:
            findings.append(make("unverified", f"Couldn't compare: {_label(r.property)}", "Values were not comparable.", severity="minor", left=left))
        elif ok:
            findings.append(make("pass", _label(r.property), detail, left=left))
        else:
            findings.append(make("fail", f"Does not meet: {_label(r.property)}", detail, left=left))
    return findings
