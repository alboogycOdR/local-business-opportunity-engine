"""Provider-neutral, source-backed Business Brief contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BusinessBriefRequest(BaseModel):
    business_id: UUID
    idempotency_key: str | None = Field(default=None, max_length=300)


class BusinessBriefFact(BaseModel):
    fact_type: str
    label: str
    value: Any = None
    source_type: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    status: str = "verified"


class BusinessBriefSection(BaseModel):
    name: str
    summary: str
    facts: list[BusinessBriefFact] = Field(default_factory=list)


class BusinessBriefOpportunity(BaseModel):
    code: str
    title: str
    description: str
    priority: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class BusinessBriefRisk(BaseModel):
    code: str
    title: str
    description: str
    severity: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class BusinessBriefRecommendedAction(BaseModel):
    code: str
    label: str
    rationale: str


class BusinessBriefResult(BaseModel):
    business_id: UUID
    score_id: UUID | None = None
    audit_run_id: UUID | None = None
    version: str = "business-brief-v1"
    summary: str
    sections: list[BusinessBriefSection] = Field(default_factory=list)
    verified_facts: list[BusinessBriefFact] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    opportunities: list[BusinessBriefOpportunity] = Field(default_factory=list)
    risks: list[BusinessBriefRisk] = Field(default_factory=list)
    recommended_action: BusinessBriefRecommendedAction
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
