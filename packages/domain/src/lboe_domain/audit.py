"""Provider-neutral digital presence audit contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field


class AuditRequest(BaseModel):
    business_id: UUID
    website_url: str | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_pages: int = Field(default=2, ge=1, le=3)
    idempotency_key: str | None = Field(default=None, max_length=300)


class AuditEvidence(BaseModel):
    kind: str
    value: Any = None
    selector: str | None = None
    page_url: str | None = None


class AuditFinding(BaseModel):
    code: str
    category: str
    status: str
    severity: str = "info"
    deterministic: bool = True
    observed_value: Any = None
    evidence: list[AuditEvidence] = Field(default_factory=list)
    source_url: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=1.0, ge=0, le=1)
    auditor_version: str = "sprint3-playwright-v1"


class WebsiteResolutionResult(BaseModel):
    requested_url: str
    normalized_url: str | None = None
    final_url: str | None = None
    http_status: int | None = None
    status: str
    error: str | None = None
    redirects: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditArtifact(BaseModel):
    kind: str
    path: str
    mime_type: str
    byte_size: int | None = None


class AuditResult(BaseModel):
    website: WebsiteResolutionResult
    findings: list[AuditFinding] = Field(default_factory=list)
    artifacts: list[AuditArtifact] = Field(default_factory=list)
    technical_metadata: dict[str, Any] = Field(default_factory=dict)
    auditor_version: str = "sprint3-playwright-v1"


class AuditAdapter(Protocol):
    async def audit(self, request: AuditRequest) -> AuditResult: ...


class FakeAuditAdapter:
    """Deterministic adapter for tests and local development."""

    def __init__(self, result: AuditResult | None = None) -> None:
        self.result = result or AuditResult(
            website=WebsiteResolutionResult(
                requested_url="https://example.test",
                normalized_url="https://example.test",
                final_url="https://example.test",
                status="healthy",
                http_status=200,
            ),
            findings=[
                AuditFinding(
                    code="WEBSITE_HEALTHY",
                    category="availability",
                    status="detected",
                    severity="info",
                    source_url="https://example.test",
                )
            ],
        )

    async def audit(self, request: AuditRequest) -> AuditResult:
        return self.result.model_copy(deep=True)
