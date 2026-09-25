"""Provider-neutral contracts for consent and outreach readiness."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ConsentBasis = Literal[
    "manual_operator_review",
    "existing_relationship",
    "explicit_permission_recorded",
    "public_business_contact_for_manual_outreach",
    "do_not_contact",
    "unknown",
]
ReadinessDecision = Literal[
    "prepare_consent_review",
    "approve_for_manual_outreach",
    "reject_outreach",
    "request_draft_changes",
    "suppress_business",
]
ReadinessChannel = Literal["email", "whatsapp", "phone_script", "manual_note"]


class OutreachReadinessRequest(BaseModel):
    outreach_draft_package_id: uuid.UUID
    decision: ReadinessDecision
    reviewer: str = Field(min_length=1, max_length=200)
    selected_channels: list[ReadinessChannel] = Field(default_factory=list)
    consent_basis_type: ConsentBasis = "unknown"
    consent_basis_notes: str = ""
    notes: str = ""
    idempotency_key: str | None = Field(default=None, max_length=200)


class OutreachChannelApproval(BaseModel):
    channel: ReadinessChannel
    outreach_draft_message_id: uuid.UUID | None = None
    approved: bool
    notes: str | None = None


class OutreachReadinessCheck(BaseModel):
    code: str
    passed: bool
    notes: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class OutreachReadinessDecision(BaseModel):
    decision: ReadinessDecision
    reviewer: str
    notes: str = ""


class OutreachReadinessResult(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    outreach_draft_package_id: uuid.UUID
    decision: ReadinessDecision
    selected_channels: list[ReadinessChannel]
    consent_basis_type: ConsentBasis
    consent_basis_notes: str
    checks: list[OutreachReadinessCheck]
    reviewer: str
    notes: str
    resulting_business_state: str
    created_at: datetime
