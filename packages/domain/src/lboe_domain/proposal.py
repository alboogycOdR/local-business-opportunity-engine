"""Provider-neutral contracts for deterministic proposal packs."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProposalType = Literal[
    "starter_website_build",
    "website_refresh",
    "conversion_upgrade",
    "technical_cleanup",
    "care_plan",
    "custom_manual_scope",
]
ProposalDecision = Literal["approve", "reject", "request_changes", "archive"]


class ProposalEvidenceRef(BaseModel):
    source_type: str
    source_id: str | None = None
    code: str | None = None
    description: str
    confidence: float = Field(default=1, ge=0, le=1)


class ProposalSection(BaseModel):
    section_type: str
    heading: str
    body: str
    sort_order: int
    evidence: list[ProposalEvidenceRef] = []


class ProposalLineItem(BaseModel):
    code: str
    label: str
    description: str
    quantity: int = 1
    unit: str = "placeholder"
    pricing_status: str = "placeholder"


class ProposalAssumption(BaseModel):
    code: str
    text: str
    category: str = "assumption"


class ProposalGenerationRequest(BaseModel):
    business_id: uuid.UUID
    proposal_type: ProposalType | None = None
    operator_requested: bool = False
    idempotency_key: str | None = None


class ProposalPackageResult(BaseModel):
    proposal_id: uuid.UUID
    business_id: uuid.UUID
    proposal_type: ProposalType
    status: str
    sections: list[ProposalSection]
    line_items: list[ProposalLineItem]
    assumptions: list[ProposalAssumption]
    evidence: list[ProposalEvidenceRef]
    created_at: datetime


class ProposalReviewRequest(BaseModel):
    decision: ProposalDecision
    reviewer: str = Field(min_length=1)
    notes: str = ""
    checks: dict[str, bool] = {}


class ProposalReviewResult(BaseModel):
    proposal_id: uuid.UUID
    decision: ProposalDecision
    status: str
    checks: dict[str, bool]
    reviewer: str
    created_at: datetime


class ProposalExportResult(BaseModel):
    proposal_id: uuid.UUID
    status: str
    files: dict[str, str]
    created_at: datetime
