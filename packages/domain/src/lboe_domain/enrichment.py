"""Provider-neutral, source-aware enrichment contracts."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field


class EnrichmentRequest(BaseModel):
    business_id: UUID
    website_url: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=300)


class EnrichmentEvidence(BaseModel):
    source_url: str | None = None
    locator: str | None = None
    excerpt: str | None = None
    observed_at: datetime


class EnrichmentFact(BaseModel):
    business_id: UUID
    source_type: str
    source_url: str | None = None
    fact_type: str
    value: str
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime
    evidence: list[EnrichmentEvidence] = Field(default_factory=list)
    policy: str = "persistent"


class EnrichmentResult(BaseModel):
    facts: list[EnrichmentFact] = Field(default_factory=list)
    adapter_version: str
    status: str = "succeeded"


class EnrichmentAdapter(Protocol):
    async def enrich(self, request: EnrichmentRequest) -> EnrichmentResult: ...


class FakeEnrichmentAdapter:
    def __init__(self, facts: list[EnrichmentFact] | None = None) -> None:
        self.facts = facts or []

    async def enrich(self, request: EnrichmentRequest) -> EnrichmentResult:
        return EnrichmentResult(
            facts=[fact.model_copy(update={"business_id": request.business_id}) for fact in self.facts],
            adapter_version="fake-enrichment-v1",
        )


def _fact(value: Any, **kwargs: Any) -> EnrichmentFact:
    return EnrichmentFact(value=str(value), **kwargs)
