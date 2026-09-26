"""Provider-neutral contracts for operator-entered CRM events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CrmEventType = Literal[
    "reply_received",
    "meeting_scheduled",
    "proposal_sent",
    "won",
    "lost",
    "no_response_note",
    "manual_note",
]
CrmChannel = Literal["email", "whatsapp", "phone", "in_person", "manual_note"]


class LeadResponseLogRequest(BaseModel):
    outreach_execution_record_id: uuid.UUID | None = None
    event_type: CrmEventType
    channel: CrmChannel
    operator: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    summary: str = ""
    notes: str = ""
    next_step: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class LeadNextStep(BaseModel):
    value: str


class LeadCrmOutcome(BaseModel):
    event_type: CrmEventType
    resulting_business_state: str


class LeadCrmEvent(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    outreach_execution_record_id: uuid.UUID | None = None
    event_type: CrmEventType
    channel: CrmChannel
    operator: str
    occurred_at: datetime
    summary: str
    notes: str
    next_step: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    resulting_business_state: str
    created_at: datetime


class LeadResponseLogResult(LeadCrmEvent):
    pass
