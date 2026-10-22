"""Step 4a: compare claims to requirements in plain code. No model, no guessing."""

from __future__ import annotations

import re
import unicodedata
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
    if isinstance(value, str) and re.search(r"\b(or|to)\b", value, re.I):
        return None  # a range or alternatives cannot be treated as the first number
    n = to_number(value)
    if n is None:
        return None
    if unit and unit.lower() in UNIT_TO_BASE:
        return n * UNIT_TO_BASE[unit.lower()][1]
    return n


def _text(value) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", str(value)).casefold())


def _as_list(value) -> list[str]:
    if value is None:
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def _mentions(value: str, wanted: str) -> bool:
    wanted = _text(wanted)
    if not wanted:
        return False
    pattern = r"(?<![\w.])" + r"[\W_]*".join(map(re.escape, wanted)) + r"(?!\w|[.,]\d)"
    return re.search(pattern, unicodedata.normalize("NFKC", value).casefold()) is not None


OPERATOR_WORDS = {"gte": "at least", "lte": "at most", "eq": "exactly"}


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


def properties_for(requirements: list[Requirement]) -> list[str]:
    """Spec dependencies plus known performance properties used to compare revisions."""
    return sorted(set(LABELS) | {r.property for r in requirements} |
                  {str(r.value) for r in requirements if r.operator == "eq_ref"})


def _label(prop: str) -> str:
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
        scoped = by_prop.get(r.property, [])
        variants = [c.variant for c in scoped if c.variant]
        found = [c for c in scoped if not c.variant]
        claim = found[0] if found else None
        ref = f"{r.section} {r.paragraph}".strip()
        related: list[str] = []  # other claims the comparison used (eq_ref)
        alternatives = None
        left_label, right_label = ("Job needs", "Listing covers") if r.check == "validity" else ("Spec requires", "Submitted")

        def make(verdict: str, title: str, detail: str = "", severity: Optional[str] = None,
                 left=None, right=None) -> Finding:
            shown = right if right is not None else alternatives
            if shown is None:
                shown = (claim.value if isinstance(claim.value, list) else _fmt(claim.value, claim.unit)) if claim else "Not stated"
            return Finding(
                id=f"{r.check}-{r.id}",
                check=r.check,
                verdict=verdict,
                severity="info" if verdict in ("pass", "not_applicable", "pending") else (severity or r.severity),
                title=title,
                detail=detail,
                requirement_id=r.id,
                claim_id=claim.id if claim else None,
                claim_ids=[claim.id, *related] if claim else [],
                spec_ref=ref,
                compare=Compare(left_label=left_label, left_value=left if left is not None else _wanted(r),
                                right_label=right_label, right_value=shown,
                                verdict="unverified" if verdict in ("unverified", "pending") else "pass" if verdict == "pass" else "fail"),
            )

        if r.applies_to and roles and not set(r.applies_to) & roles:
            findings.append(make("not_applicable", _label(r.property), f"Applies to {', '.join(r.applies_to)} only."))
            continue

        if r.operator == "exists" and found:
            findings.append(make("pass", _label(r.property), right="Included"))
            continue

        if r.operator == "eq_ref" and (claim is None or not by_prop.get(str(r.value))):
            assembly = {r.property, str(r.value)} == {"t_rating_hr", "f_rating_hr"}
            product_only = roles and "product_data" in roles and not roles & {"system_drawing", "listing", "test_report"}
            if assembly and product_only:
                findings.append(make("pending", "Pending assembly proof",
                                     "Product data does not establish a specific assembly's F/T ratings. Confirm the listed assembly separately."))
            else:
                findings.append(make("unverified", f"Not stated: {_label(r.property)}",
                                     "Both quoted ratings are needed for this comparison.", severity="minor"))
            continue

        if claim is None:
            if variants:
                findings.append(make("unverified", f"Option not confirmed: {_label(r.property)}",
                                     f"Quoted values apply only to {', '.join(dict.fromkeys(variants))}. Confirm the submitted configuration.",
                                     severity="minor", right="Option dependent"))
            else:
                findings.append(make("unverified", f"Not stated: {_label(r.property)}", r.text, severity="minor"))
            continue

        ok: Optional[bool] = None
        detail = ""
        left = None
        if r.operator in ("gte", "lte", "eq"):
            numbers, b = [normalize(c.value, c.unit) for c in found], normalize(r.value, r.unit)
            if all(a is not None for a in numbers) and b is not None:
                outcomes = [{"gte": a >= b, "lte": a <= b, "eq": abs(a - b) < 1e-9}[r.operator] for a in numbers]
                ok = outcomes[0] if len(set(outcomes)) == 1 else None
                if len(found) > 1:
                    alternatives = [_fmt(c.value, c.unit) for c in found]
                    related = [c.id for c in found[1:]]
                detail = ("Stated alternatives give different outcomes; confirm the submitted configuration." if ok is None else
                          f"Package states {alternatives or _fmt(claim.value, claim.unit)}; spec requires {OPERATOR_WORDS[r.operator]} {_fmt(r.value, r.unit)}.")
        elif r.operator == "eq_ref":
            other = [c for c in by_prop.get(str(r.value), []) if not c.variant]
            if len(found) == len(other) == 1:
                related = [other[0].id]
                a, b = normalize(claim.value, claim.unit), normalize(other[0].value, other[0].unit)
                if a is not None and b is not None:
                    ok = abs(a - b) < 1e-9
                    left = f"{_wanted(r)} ({_fmt(other[0].value, other[0].unit)})"  # "T = F (2 hr)"
                    detail = (f"{_label(r.property)} is {_fmt(claim.value, claim.unit)} but "
                              f"{_label(str(r.value))} is {_fmt(other[0].value, other[0].unit)}.")
        elif r.operator == "contains":
            have = _as_list(claim.value)
            ok = r.value is not None and any(_mentions(h, str(r.value)) for h in have)
            detail = f"Package lists {_fmt(claim.value, None)}; needs {r.value}."
        elif r.operator == "any_of":
            allowed = _as_list(r.value)
            ok = any(_mentions(h, a) or (_mentions(a, h) and _mentions(c.quote or "", a))
                     for c in found for h in _as_list(c.value) for a in allowed)
            detail = f"Package states {_fmt(claim.value, None)}; allowed: {_fmt(r.value, None)}."

        if ok is None:
            findings.append(make("unverified", f"Couldn't compare: {_label(r.property)}", detail or "Values were not comparable.", severity="minor", left=left))
        elif ok:
            findings.append(make("pass", _label(r.property), detail, left=left))
        else:
            findings.append(make("fail", f"Does not meet: {_label(r.property)}", detail, left=left))
    return findings
