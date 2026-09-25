"""Provider-neutral Opportunity Score v1 contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ScoreBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedNextAction(StrEnum):
    ARCHIVE = "archive"
    MANUAL_REVIEW = "manual_review"
    AUDIT_REQUIRED = "audit_required"
    SCORE_ONLY = "score_only"
    GENERATE_DEMO = "generate_demo"
    CONVERSION_UPGRADE_OFFER = "conversion_upgrade_offer"
    TECHNICAL_CLEANUP_OFFER = "technical_cleanup_offer"
    DO_NOT_CONTACT = "do_not_contact"


class OpportunityScoreRequest(BaseModel):
    business_id: UUID
    idempotency_key: str | None = Field(default=None, max_length=300)


class OpportunityScoreComponent(BaseModel):
    code: str
    points: int
    category: str
    max_points: int
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_type: str = "derived"
    confidence: float = Field(default=1.0, ge=0, le=1)


class OpportunityScoreHold(BaseModel):
    code: str
    reason: str
    severity: str = "high"
    evidence: dict[str, Any] = Field(default_factory=dict)


class OpportunityScoreResult(BaseModel):
    business_id: UUID
    score: int = Field(ge=0, le=100)
    band: ScoreBand
    version: str = "opportunity-v1"
    components: list[OpportunityScoreComponent] = Field(default_factory=list)
    holds: list[OpportunityScoreHold] = Field(default_factory=list)
    recommended_next_action: RecommendedNextAction
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
