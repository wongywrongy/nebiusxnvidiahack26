"""Data shapes shared by the pipeline, the API and the model calls.

Model outputs are validated against these. Keep field descriptions short: they are sent
to the model as part of the JSON schema.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

Value = Union[float, str, list[str], None]

# ---------- extraction ----------


class PageLabel(BaseModel):
    page: int
    kind: Literal[
        "cover", "product_data", "listing", "system_drawing", "test_report", "installation", "warranty", "other"
    ]


class TriageOut(BaseModel):
    pages: list[PageLabel]


class Requirement(BaseModel):
    id: str
    section: str = Field(description="Spec section, e.g. 07 84 00")
    paragraph: str = Field(description="Spec paragraph reference, e.g. 2.1.A")
    property: str = Field(description="snake_case property name, e.g. t_rating_hr")
    operator: Literal["gte", "lte", "eq", "eq_ref", "contains", "any_of", "exists"]
    value: Value = Field(default=None, description="Target value; for eq_ref the name of the other property")
    unit: Optional[str] = None
    text: str = Field(description="Plain-language requirement")
    severity: Literal["critical", "major", "minor"] = "major"
    check: Literal["spec", "validity", "completeness"] = "spec"
    applies_to: list[str] = Field(default=[], description="Submittal roles it applies to (product_data, system_drawing); empty = all")


class RequirementsOut(BaseModel):
    requirements: list[Requirement]


class Claim(BaseModel):
    id: str
    product: str
    manufacturer: str
    model: Optional[str] = None
    property: str = Field(description="snake_case property name matching requirement properties")
    value: Value
    unit: Optional[str] = None
    page: Optional[int] = None
    bbox: Optional[list[float]] = None
    quote: Optional[str] = Field(default=None, description="Short text from the page supporting the claim")


class ClaimsOut(BaseModel):
    product: str
    manufacturer: str
    model: Optional[str] = None
    document_revision: Optional[str] = Field(default=None, description="Revision or date printed on the sheet")
    claims: list[Claim]


# ---------- verification ----------


class Evidence(BaseModel):
    url: str
    tier: Literal["manufacturer", "listing_body", "distributor", "archive", "agency", "other"]
    title: str
    retrieved_at: Optional[str] = None
    sha256: Optional[str] = None
    excerpt: Optional[str] = None


class PropertyValue(BaseModel):
    property: str
    value: Value
    unit: Optional[str] = None
    quote: Optional[str] = Field(default=None, description="Exact text from the source stating this value")


class VerifyOut(BaseModel):
    """What the model concluded after reading the web sources for one product."""

    status: Literal["active", "discontinued", "unknown"]
    replacement: Optional[str] = None
    current_revision: Optional[str] = Field(default=None, description="Revision or date exactly as printed on the source")
    status_date: Optional[str] = Field(default=None, description="Date it was discontinued or replaced, as stated")
    status_quote: Optional[str] = Field(default=None, description="Exact text from the source stating the status")
    current_values: list[PropertyValue] = []
    source_urls: list[str] = []
    notes: Optional[str] = None


class CompareRow(BaseModel):
    property: str
    label: str
    submitted: Optional[str]
    current: Optional[str]
    changed: bool
    source_url: Optional[str] = None  # where the current value was quoted from
    quote: Optional[str] = None


# ---------- findings and result ----------

class Highlight(BaseModel):
    """Where one claim behind a finding sits in the submittal."""

    claim_id: str
    doc_file: Optional[str] = None  # path under data/raw/; None when the PDF is not downloaded
    page: Optional[int] = None  # page in doc_file (package page when doc_file is None)
    quote: Optional[str] = None
    boxes: list[dict[str, float]] = []  # {x0, y0, x1, y1} as fractions of the page; [] = not located
    kind: Literal["problem", "checked"] = "problem"


Check = Literal["spec", "currency", "validity", "status", "completeness"]
Verdict = Literal["pass", "fail", "outdated", "unverified", "note", "not_applicable"]
Severity = Literal["critical", "major", "minor", "info"]
Decision = Literal["approve", "approve_with_note", "send_back"]


class Compare(BaseModel):
    """One side-by-side comparison per finding, built in code. Values may be lists (shown as chips)."""

    left_label: str
    left_value: Value = None
    right_label: str
    right_value: Value = None
    verdict: Literal["fail", "pass", "changed"]
    rows: list[CompareRow] = []  # currency: only the fields whose values differ


class FixCheck(BaseModel):
    label: str
    ok: Optional[bool]  # None: not stated in the candidate's document
    note: str = ""


class FixCandidate(BaseModel):
    name: str
    source_url: str
    checks: list[FixCheck] = []
    passes: bool


class Fix(BaseModel):
    """What to send instead: candidates found online, each run through the same checks as a new submittal."""

    head: str
    query: str = ""  # what was searched, so "nothing passed" still shows what was tried
    candidates: list[FixCandidate] = []
    suggest: str = ""  # the best passing candidate, "" when none passes


class Finding(BaseModel):
    id: str
    check: Check
    verdict: Verdict
    severity: Severity
    title: str = Field(description="Plain language, no jargon")
    detail: str = ""
    why_it_matters: Optional[str] = None
    requirement_id: Optional[str] = None
    claim_id: Optional[str] = None
    claim_ids: list[str] = []  # claims on the page that this finding is about
    highlights: list[Highlight] = []
    compare: Optional[Compare] = None
    spec_ref: Optional[str] = None
    evidence: list[Evidence] = []
    decided_by: str = "code"
    fix: Optional[Fix] = None


class ReportOut(BaseModel):
    summary: str = Field(description="One or two plain-language sentences")
    note_to_subcontractor: str
    finding_titles: dict[str, str] = Field(default={}, description="Plain-language title per finding id")
    why_it_matters: dict[str, str] = {}


class Usage(BaseModel):
    task: str
    tier: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    cached: bool = False
    format: Optional[str] = None  # live: "json_schema" or "json_object" (fallback)


class Result(BaseModel):
    case_id: str
    title: str
    decision: Decision
    summary: str
    findings: list[Finding]
    comparison: list[CompareRow] = []
    claims: list[Claim] = []
    document_revision: Optional[str] = None
    note_to_subcontractor: str = ""
    usage: list[Usage] = []
    web_credits: float = 0.0
    duration_ms: int = 0

    @property
    def cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.usage)


# ---------- streaming ----------

# "reconcile" only appears in older recorded runs (replay); new runs don't emit it.
Stage = Literal["queued", "ingest", "triage", "extract", "spec_check", "verify", "reconcile", "fix", "report", "done", "error"]


class Event(BaseModel):
    run_id: str
    case_id: Optional[str] = None
    t_ms: int = Field(description="Milliseconds since the run started")
    stage: Stage
    message: str
    model: Optional[str] = None
    data: Optional[dict] = None
