"""Provider-neutral contracts for operator-recorded manual outreach."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ExecutionChannel = Literal["email", "whatsapp", "phone_script", "manual_note"]


class ManualOutreachLogRequest(BaseModel):
    outreach_draft_package_id: uuid.UUID
    outreach_draft_message_id: uuid.UUID
    channel: ExecutionChannel
    operator: str = Field(min_length=1, max_length=200)
    sent_at: datetime
    external_reference: str | None = Field(default=None, max_length=500)
    notes: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class OutreachExecutionEvidence(BaseModel):
    source: str
    reference: str | None = None
    notes: str | None = None


class OutreachExecutionRecord(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    outreach_draft_package_id: uuid.UUID
    outreach_draft_message_id: uuid.UUID
    channel: ExecutionChannel
    operator: str
    sent_at: datetime
    external_reference: str | None = None
    notes: str
    evidence: dict[str, Any]
    resulting_business_state: str
    created_at: datetime
    delivery_performed_by_system: bool = False


class ManualOutreachLogResult(OutreachExecutionRecord):
    pass
