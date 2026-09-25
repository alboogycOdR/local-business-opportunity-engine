"""Provider-neutral contracts for safe concept demos."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DemoType = Literal[
    "starter_website",
    "website_refresh",
    "conversion_upgrade",
    "technical_cleanup_preview",
]


class DemoGenerationRequest(BaseModel):
    business_id: uuid.UUID
    brief_id: uuid.UUID | None = None
    demo_type: DemoType | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


class DemoSection(BaseModel):
    section_type: str
    heading: str
    body: str
    sort_order: int
    evidence: dict[str, Any] = Field(default_factory=dict)


class DemoClaim(BaseModel):
    claim_text: str
    claim_type: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    approved: bool = False


class DemoArtifact(BaseModel):
    kind: str
    path: str
    mime_type: str
    byte_size: int


class DemoQaResult(BaseModel):
    status: Literal["passed", "failed"]
    checks: dict[str, Any]
    created_at: datetime | None = None


class GeneratedDemo(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    brief_id: uuid.UUID
    score_id: uuid.UUID | None = None
    audit_run_id: uuid.UUID | None = None
    version: str
    demo_type: DemoType
    status: str
    preview_path: str
    preview_url: str | None = None
    sections: list[DemoSection] = Field(default_factory=list)
    claims: list[DemoClaim] = Field(default_factory=list)
    artifacts: list[DemoArtifact] = Field(default_factory=list)
    qa: DemoQaResult | None = None
    created_at: datetime
