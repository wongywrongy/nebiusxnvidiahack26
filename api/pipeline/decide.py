"""The decision (in code, from the findings) and the plain-language result (Super writes the words only).

No model reviews or drops findings: every finding stands on its quoted evidence.
"""

from __future__ import annotations

import json
from typing import Optional

from ..llm import router
from ..schemas import Decision, Finding, ReportOut, Usage

FLAGGED = ("fail", "outdated")


def decide(findings: list[Finding]) -> Decision:
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
                    "and one sentence on why each issue matters on site. Where an issue has a suggested_fix, name it in the note.\n\n"
                    + json.dumps({"submittal": title, "decision": decision,
                                  "issues": [{**f.model_dump(include={"id", "title", "detail", "spec_ref"}),
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
    return out, [usage]
