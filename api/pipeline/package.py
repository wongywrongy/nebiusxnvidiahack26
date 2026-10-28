"""The package view: every submittal in a run as one row of a compliance matrix, derived in code.

A reviewer (or the architect) looks at the whole package at once: does each item meet the spec, is the sheet
current, is the product still made, what should the sub send, and which items need a person to look closer.
Nothing here calls a model; every cell comes from findings that already carry their quotes.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import Alternate, Finding, PackageRow, PackageSummary, Result

SPEC_CHECKS = ("spec", "validity", "completeness")

# Display wording close to what reviewers stamp; the decision itself is unchanged.
STAMP = {
    "approve": "No exceptions taken",
    "approve_with_note": "Exceptions noted",
    "send_back": "Revise and resubmit",
    "not_applicable": "Not reviewed: doesn't match this spec",
}


def _requirement_findings(result: Result) -> list[Finding]:
    return [f for f in result.findings if f.check in SPEC_CHECKS and f.requirement_id and f.verdict != "not_applicable"]


def counts(result: Result) -> tuple[int, int, int]:
    """(meets, doesn't meet, couldn't confirm) over the spec requirements that apply."""
    rf = _requirement_findings(result)
    return (sum(f.verdict == "pass" for f in rf), sum(f.verdict == "fail" for f in rf),
            sum(f.verdict in ("unverified", "pending") for f in rf))


def best_alternate(result: Result) -> Optional[Alternate]:
    """The top-ranked alternate across all fixes on this item, if it isn't a failed one."""
    alts = [a for f in result.findings if f.fix for a in f.fix.alternates]
    alts = [a for a in alts if a.rank != "failed"]
    order = {"meets_spec": 0, "possible": 1}
    return min(alts, key=lambda a: (order[a.rank], len(a.confirm)), default=None)


def _lc(text: str) -> str:
    """Lower-case the first letter only, so "VOC (air quality)" keeps its acronym."""
    return text if text[1:2].isupper() else text[:1].lower() + text[1:]


def what_to_send(f: Finding) -> Optional[str]:
    """One plain line per finding that needs action. Templates only: no model writes these."""
    left = f.compare.left_value if f.compare else None
    wanted = ", ".join(map(str, left)) if isinstance(left, list) else (str(left) if left not in (None, "") else "")
    label = f.title.removeprefix("Does not meet: ").removeprefix("Couldn't confirm: ")
    if f.id == "status-discontinued":
        return "A current product that meets the spec (this one is discontinued)"
    if f.id == "currency-outdated":
        return "The manufacturer's current data sheet"
    if f.id == "currency-newer":
        return "The newer data sheet (optional)"
    if f.configure:
        return specify(f)
    if f.verdict == "fail" and f.check == "validity":
        return f"A listing that covers {wanted}" if wanted else "A listing that covers this job condition"
    if f.verdict == "fail" and f.check == "spec":
        if "=" in wanted and "≤" not in wanted and "≥" not in wanted:
            return f"A listed system with {wanted}"  # eq_ref, e.g. "T = F (2 hr)"
        return f"A product with {_lc(label)} {wanted}".strip()
    if f.verdict in ("unverified", "pending") and f.check in SPEC_CHECKS and f.severity in ("critical", "major"):
        return f"Data showing {_lc(label)}"
    return None


def specify(f: Finding) -> str:
    """"Specify EZ1 → dims down to 1 % (spec ≤ 5 %)": the ordering option whose quoted value meets the rule."""
    names = " or ".join(dict.fromkeys(o.option for o in f.configure))
    wanted = f.compare.left_value if f.compare else None
    spec = f" (spec {', '.join(map(str, wanted)) if isinstance(wanted, list) else wanted})" if wanted not in (None, "") else ""
    return f"Specify {names} → {_lc(f.title.removeprefix('Specify option: '))} {f.configure[0].value}{spec}"


def _confirm(a: Alternate) -> str:
    return ", ".join(map(_lc, a.confirm))


def _ref(case: dict, result: Result) -> str:
    return " ".join(x for x in (case.get("number"), case.get("title") or result.title) if x)


def return_note(case: dict, result: Result, asks: list[str], specs: list[str], best: Optional[Alternate],
                proposal: Optional[str]) -> str:
    """The draft to the sub, from code only: what to send, options to specify, and at most one alternate."""
    lines = [f"Revise and resubmit {_ref(case, result)}.", "", "Please send:"]
    lines += [f"{i}. {a}" for i, a in enumerate(asks[:4], 1)] or ["1. A product that meets the spec"]
    lines += specs[:2]
    if best and best.rank == "meets_spec":
        lines.append(f"Acceptable alternate: {best.name}" + (f", configured as {proposal}; confirm before ordering." if proposal else "."))
    elif best:
        lines.append(f"Possible alternate to confirm: {best.name} ({_confirm(best)}).")
    return "\n".join(lines)


def approval_note(case: dict, result: Result, specs: list[str], unconfirmed: list[str]) -> str:
    """The draft to the architect: the stamp, options the order must name, and what couldn't be confirmed."""
    stamp = STAMP["approve" if result.decision == "approve" else "approve_with_note"]
    lines = [f"Please review {_ref(case, result)} for approval: {stamp.lower()}."]
    lines += specs[:3]
    if unconfirmed:
        lines.append(f"Not confirmed: {', '.join(map(_lc, unconfirmed[:4]))}.")
    return "\n".join(lines)


def row(case: dict, result: Result) -> PackageRow:
    rf = _requirement_findings(result)
    by_id = {f.id: f for f in result.findings}
    if result.decision == "not_applicable":
        spec = "not_checked"
    elif any(f.verdict == "fail" for f in rf):
        spec = "fails"
    elif any(f.configure for f in rf):
        spec = "configure"
    elif any(f.verdict in ("unverified", "pending") for f in rf):
        spec = "unconfirmed"
    else:
        spec = "meets"
    current = ("outdated" if "currency-outdated" in by_id else "current" if "currency-current" in by_id
               else "newer" if "currency-newer" in by_id else "unknown")
    # "unknown": the web check ran and couldn't confirm; "not_checked": no web check ran for this item.
    web_ran = result.decision != "not_applicable" and any(f.check in ("currency", "status") for f in result.findings)
    made = ("discontinued" if "status-discontinued" in by_id else "active" if "status-active" in by_id
            else "unknown" if web_ran else "not_checked")
    meets, fails, unconfirmed = counts(result)
    unconfirmed_plain = sum(f.verdict in ("unverified", "pending") and not f.configure for f in rf)
    # Most important first: product status, then the sheet, then spec failures, then configuration notes.
    # A discontinued product makes its ordering options moot, so those lines are dropped.
    order = {"status": 0, "currency": 1, "validity": 2, "spec": 3, "completeness": 4}
    acting = sorted((f for f in result.findings if f.verdict not in ("pass", "not_applicable")),
                    key=lambda f: (order.get(f.check, 5), bool(f.configure)))
    asks = list(dict.fromkeys(a for f in acting if not f.configure if (a := what_to_send(f))))
    specs = [] if made == "discontinued" else list(dict.fromkeys(specify(f) for f in acting if f.configure))
    best = best_alternate(result)
    actions = asks + specs
    if best and best.rank == "meets_spec":
        actions.insert(0, f"Send {best.name} (meets the spec)")
    elif best:
        actions.append(f"Possible alternate: {best.name}; confirm {_confirm(best)}")
    proposal = next((c.selection.model for f in result.findings if f.fix for c in f.fix.candidates
                     if best and c.source_url == best.source_url and c.selection
                     and c.selection.origin == "agent_proposal"), None)
    unconfirmed_labels = [f.title.removeprefix("Couldn't confirm: ") for f in rf
                          if f.verdict in ("unverified", "pending") and not f.configure]
    return PackageRow(case_id=result.case_id, title=case.get("title") or result.title, number=case.get("number"),
                      sender=case.get("from"), decision=result.decision, stamp=STAMP[result.decision], spec=spec,
                      current_sheet=current, still_made=made, meets=meets, doesnt_meet=fails,
                      couldnt_confirm=unconfirmed, what_to_send=actions[:3], best_alternate=best,
                      manual_review_suggested=result.decision in ("approve", "approve_with_note") and unconfirmed_plain >= 2,
                      return_note="" if result.decision == "not_applicable" else return_note(case, result, asks, specs, best, proposal),
                      approval_note="" if result.decision == "not_applicable" else approval_note(case, result, specs, unconfirmed_labels))


def summarize(run_id: str, items: list[tuple[dict, Result]]) -> PackageSummary:
    rows = [row(case, result) for case, result in items]
    return PackageSummary(run_id=run_id, rows=rows,
                          ready=sum(r.decision in ("approve", "approve_with_note") for r in rows),
                          need_changes=sum(r.decision == "send_back" for r in rows),
                          not_checked=sum(r.decision == "not_applicable" for r in rows),
                          manual_review_suggested=sum(r.manual_review_suggested for r in rows))
