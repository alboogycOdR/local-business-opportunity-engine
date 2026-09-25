"""Provider-neutral contracts for operator-reviewed outreach drafts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OfferType = Literal[
    "starter_website_offer",
    "website_refresh_offer",
    "conversion_upgrade_offer",
    "technical_cleanup_offer",
]
DraftChannel = Literal["email", "whatsapp", "phone_script", "manual_note"]


def default_channels() -> list[DraftChannel]:
    return ["email", "whatsapp", "phone_script", "manual_note"]


class OutreachDraftRequest(BaseModel):
    business_id: uuid.UUID
    demo_id: uuid.UUID | None = None
    channels: list[DraftChannel] = Field(default_factory=default_channels)
    idempotency_key: str | None = Field(default=None, max_length=200)


class OutreachOffer(BaseModel):
    offer_type: OfferType
    angle: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class OutreachDraftEvidence(BaseModel):
    source_type: str
    reference: str
    confidence: float = 1.0


class OutreachDraftMessage(BaseModel):
    channel: DraftChannel
    subject: str | None = None
    body: str
    tone: str = "neutral"
    evidence: list[OutreachDraftEvidence] = Field(default_factory=list)
    approved: bool = False


class OutreachDraftCheck(BaseModel):
    code: str
    passed: bool
    notes: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class OutreachDraftPackage(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    demo_id: uuid.UUID
    brief_id: uuid.UUID
    score_id: uuid.UUID | None = None
    version: str
    offer: OutreachOffer
    status: str
    messages: list[OutreachDraftMessage] = Field(default_factory=list)
    checks: list[OutreachDraftCheck] = Field(default_factory=list)
    created_at: datetime
