"""The decision (in code, from the findings) and the plain-language result (Super writes the words only).

No model reviews or drops findings: every finding stands on its quoted evidence.
"""

from __future__ import annotations

import json
from typing import Optional

from ..llm import router
from ..config import settings
from ..schemas import Decision, Finding, ReportOut, Usage

FLAGGED = ("fail", "outdated")


def decide(findings: list[Finding]) -> Decision:
    requirements = [f for f in findings if f.requirement_id]
    if requirements and all(not f.claim_ids and not f.claim_id and f.verdict in
                            ("unverified", "pending", "not_applicable") for f in requirements):
        return "not_applicable"
    active = [f for f in findings if f.verdict in FLAGGED]
    if any(f.severity in ("critical", "major") for f in active):
        return "send_back"
    if active or any(f.verdict in ("note", "unverified") for f in findings):
        return "approve_with_note"
    return "approve"


async def report(case_id: Optional[str], title: str, decision: Decision, findings: list[Finding]) -> tuple[ReportOut, list[Usage]]:
    issues = [f for f in findings if f.verdict != "pass"]
    out, usage = await router.call(
        "report",
        ReportOut,
        [
            {
                "role": "user",
                "content": (
                    "Write the result of a submittal review for a busy project engineer. Plain language, no jargon, no model names. "
                    "Give a one or two sentence summary, a short note to send to the subcontractor, a plain title for each issue, "
                    "and one sentence on why each issue matters on site. Where an issue has a suggested_fix, name it in the note. "
                    "Respect each coded verdict: unverified or not stated means missing evidence, not a failed requirement. "
                    "Different revision labels alone do not establish which document is newer. "
                    "Do not infer safety or code violations from a documentation difference.\n\n"
                    + ("This document has no matched checklist values. Write one short sentence saying it does not match this spec; do not approve or reject it.\n" if decision == "not_applicable" else "")
                    + json.dumps({"submittal": title, "decision": decision,
                                  "issues": [{**f.model_dump(include={"id", "title", "detail", "spec_ref", "verdict", "severity"}),
                                              "suggested_fix": f.fix.suggest if f.fix else None} for f in issues]})
                ),
            }
        ],
        {"case_id": case_id},
    )
    for f in findings:
        if f.id in out.finding_titles:
            f.title = out.finding_titles[f.id]
        if f.id in out.why_it_matters:
            f.why_it_matters = out.why_it_matters[f.id]
    # Verdict and coverage statements are templates: generated prose cannot broaden the review.
    lead = {"approve": "The checked product data can be approved.",
            "approve_with_note": "The product data can be approved with the clarification notes below.",
            "send_back": "Revise and resubmit to address the findings below.",
            "not_applicable": "This document does not match this spec; pick a different spec in the Inbox."}[decision]
    if decision != "not_applicable" and any(f.verdict == "pending" for f in findings):
        lead += " Assembly proof remains pending; confirm the listed assembly separately."
    if settings.live or case_id is not None:
        out.summary = lead
        details = [f"{f.title}: {f.detail}" for f in findings if f.verdict not in ("pass", "not_applicable")]
        details += [f.fix.suggest for f in findings if f.fix and any(
            c.passes and c.selection and c.selection.origin == "agent_proposal" for c in f.fix.candidates)]
        out.note_to_subcontractor = lead + ("\n\n" + "\n".join(details) if details else "")
    if decision == "not_applicable":
        out.summary = lead + (" Mock mode has no recorded answers for this PDF." if not settings.live and case_id is None else "")
        out.note_to_subcontractor = ""
    return out, [usage]
