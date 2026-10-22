"""Data shapes shared by the pipeline, the API and the model calls.

Model outputs are validated against these. Keep field descriptions short: they are sent
to the model as part of the JSON schema.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, PrivateAttr

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


class Checklist(RequirementsOut):
    """Draft provenance stays beside the requirements; only an admin-reviewed file is used live."""
    section: str = ""
    title: str = ""
    drafted_by: Optional[str] = None
    source_name: str = ""
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    drafted_at: Optional[datetime] = None
    reviewed_at: Optional[date] = None


class ReviewedChecklist(Checklist):
    reviewed_at: date


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
    variant: Optional[str] = Field(default=None, description="Exact phrase in the quote naming the optional model/driver/configuration limiting this value; null for a product-wide statement")
    scope: Literal["product_wide", "option", "unknown"] = "unknown"
    scope_quote: Optional[str] = Field(default=None, description="Exact passage establishing whether this value covers the product or only an option")
    selection_quote: Optional[str] = None


class Selection(BaseModel):
    model: str
    page: int
    quote: str = Field(description="Exact submitted passage marking the selected/submitted/specified configuration; never an ordering example")


class ClaimsOut(BaseModel):
    product: str
    manufacturer: str
    model: Optional[str] = None
    selection: Optional[Selection] = None
    family: Optional[str] = Field(default=None, description="Product family identifier printed on the submitted pages, excluding order-code options")
    family_quote: Optional[str] = Field(default=None, description="Exact submitted passage identifying this family")
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
    archived_path: Optional[str] = None
    cache_hit: Optional[bool] = None


class PropertyValue(BaseModel):
    property: str
    value: Value
    unit: Optional[str] = None
    quote: Optional[str] = Field(default=None, description="Exact text from the source stating this value")
    source_url: Optional[str] = None
    model: Optional[str] = Field(default=None, description="Exact product/model printed on this source; never copy SUBMITTED without source evidence")
    identity_quote: Optional[str] = Field(default=None, description="Exact source passage naming this product/model")
    variant: Optional[str] = Field(default=None, description="Exact quoted configuration limiting this value; null only for product-wide values")
    scope: Literal["product_wide", "option", "unknown"] = "unknown"
    scope_quote: Optional[str] = None
    selection_quote: Optional[str] = None


class VerifyOut(BaseModel):
    """What the model concluded after reading the web sources for one product."""

    status: Literal["active", "discontinued", "unknown"]
    replacement: Optional[str] = None
    current_revision: Optional[str] = Field(default=None, description="Revision or date exactly as printed on the source")
    status_date: Optional[str] = Field(default=None, description="Date it was discontinued or replaced, as stated")
    status_quote: Optional[str] = Field(default=None, description="Exact text from the source stating the status")
    status_family: Optional[str] = Field(default=None, description="Exact family name in the status quote, also named by the submitted product; status only")
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
Verdict = Literal["pass", "fail", "outdated", "unverified", "note", "not_applicable", "pending"]
Severity = Literal["critical", "major", "minor", "info"]
Decision = Literal["approve", "approve_with_note", "send_back"]


class Compare(BaseModel):
    """One side-by-side comparison per finding, built in code. Values may be lists (shown as chips)."""

    left_label: str
    left_value: Value = None
    right_label: str
    right_value: Value = None
    verdict: Literal["fail", "pass", "changed", "unverified"]
    rows: list[CompareRow] = []  # currency: only the fields whose values differ


class FixCheck(BaseModel):
    label: str
    ok: Optional[bool]  # None: not stated in the candidate's document
    note: str = ""
    requirement_id: Optional[str] = None
    evidence: list[Evidence] = []


class FixCandidate(BaseModel):
    name: str
    source_url: str
    documents: list[Evidence] = Field(default=[], max_length=3)
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
    evidence: list[Evidence] = []  # status findings: the page the quote is on comes first
    quote: Optional[str] = None  # status findings: the source's exact words
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
    reasoning_tokens: int = 0  # live: thinking tokens the server reported (Nemotron 3 thinks by default)
    thinking: Optional[str] = None  # live: "off" (asked for no thinking), "on", or "server-default"
    finish_reason: Optional[str] = None


class ToolFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


class ToolMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: list[ToolCall] = []


class InvestigationStep(BaseModel):
    n: int
    tool: str
    args: dict
    summary: str
    credits: float = 0
    ms: int = 0


class Investigation(BaseModel):
    steps: list[InvestigationStep] = []
    outcome: Literal["found", "not_found", "capped"] = "not_found"
    purpose: Literal["primary", "replacement"] = "primary"
    resolution: Literal["not_resolved", "revision_only", "values_confirmed", "problem_found"] = "not_resolved"
    # Whole extracted pages stay internal; the public trace contains only short, redacted summaries.
    _pages: list[dict] = PrivateAttr(default_factory=list)
    _usage: list[Usage] = PrivateAttr(default_factory=list)
    _verified: VerifyOut = PrivateAttr(default_factory=lambda: VerifyOut(status="unknown"))
    _document_url: Optional[str] = PrivateAttr(default=None)
    _document_title: str = PrivateAttr(default="")


class Diagnostic(BaseModel):
    stage: str
    kind: Literal["budget", "provider", "output_limit", "internal"]
    message: str


class Result(BaseModel):
    case_id: str
    title: str
    decision: Decision
    summary: str
    findings: list[Finding]
    comparison: list[CompareRow] = []
    claims: list[Claim] = []
    selection: Optional[Selection] = None
    document_revision: Optional[str] = None
    note_to_subcontractor: str = ""
    usage: list[Usage] = []
    web_credits: float = 0.0
    duration_ms: int = 0
    investigation: Optional[Investigation] = None
    investigations: list[Investigation] = []
    mode: Optional[Literal["mock", "live"]] = None
    replayed_from: Optional[str] = None
    warnings: list[str] = []
    diagnostics: list[Diagnostic] = []
    validity: Literal["valid", "invalid", "legacy"] = "legacy"
    config_hash: Optional[str] = None
    fresh_model_cost_usd: float = 0.0
    fresh_web_credits: float = 0.0
    queue_ms: int = 0
    ocr_pages: int = 0
    archived_submittals: list[str] = []
    evidence_label: Optional[str] = None
    claims_extracted: int = 0
    claims_kept: int = 0
    web_values_read: int = 0
    web_values_kept: int = 0

    @property
    def cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.usage)


# ---------- streaming ----------

Stage = Literal["queued", "ingest", "triage", "extract", "spec_check", "verify", "investigate", "fix", "report", "done", "error"]


class Event(BaseModel):
    run_id: str
    case_id: Optional[str] = None
    t_ms: int = Field(description="Milliseconds since the run started")
    stage: Stage
    message: str
    model: Optional[str] = None
    data: Optional[dict] = None
