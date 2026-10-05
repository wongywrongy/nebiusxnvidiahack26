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


class VerifyOut(BaseModel):
    """What the model concluded after reading the web sources for one product."""

    status: Literal["active", "discontinued", "unknown"]
    replacement: Optional[str] = None
    current_revision: Optional[str] = None
    current_values: list[PropertyValue] = []
    source_urls: list[str] = []
    notes: Optional[str] = None


class CompareRow(BaseModel):
    property: str
    label: str
    submitted: Optional[str]
    current: Optional[str]
    changed: bool


# ---------- findings and result ----------

Check = Literal["spec", "currency", "validity", "status", "completeness"]
Verdict = Literal["pass", "fail", "outdated", "unverified", "note"]
Severity = Literal["critical", "major", "minor", "info"]
Decision = Literal["approve", "approve_with_note", "send_back"]


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
    spec_ref: Optional[str] = None
    evidence: list[Evidence] = []
    decided_by: str = "code"


class ReconcileOut(BaseModel):
    """Ultra reviews flagged findings: keep, drop as false positive, or adjust severity."""

    keep: list[str] = Field(description="Finding ids that stand")
    drop: list[str] = Field(default=[], description="Finding ids that are false positives")
    rationale: str


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
    note_to_subcontractor: str = ""
    usage: list[Usage] = []
    web_credits: float = 0.0
    duration_ms: int = 0

    @property
    def cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.usage)


# ---------- streaming ----------

Stage = Literal["queued", "ingest", "triage", "extract", "spec_check", "verify", "reconcile", "report", "done", "error"]


class Event(BaseModel):
    run_id: str
    case_id: Optional[str] = None
    t_ms: int = Field(description="Milliseconds since the run started")
    stage: Stage
    message: str
    model: Optional[str] = None
    data: Optional[dict] = None
