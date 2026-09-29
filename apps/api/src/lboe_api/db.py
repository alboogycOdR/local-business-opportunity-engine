"""Database configuration and Sprint 1 persistence models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON, TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every dialect.

    The PostgreSQL migrations declare ``TIMESTAMPTZ``. SQLite's ``create_all`` test schema
    has no timezone-aware storage type, so it drops offsets. Normalising to UTC on the way in
    and attaching UTC on the way out keeps instants unambiguous across both dialects; a
    follow-up due "09:00+02:00" is stored as 07:00 UTC and displayed as 09:00 SAST.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


JsonType = JSON().with_variant(JSONB, "postgresql")


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    vertical: Mapped[str] = mapped_column(String(100))
    geography: Mapped[str | None] = mapped_column(String(200), nullable=True)
    policy: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class PilotRun(Base):
    __tablename__ = "pilot_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    vertical: Mapped[str] = mapped_column(String(100))
    geography: Mapped[str] = mapped_column(String(200))
    target_lead_count: Mapped[int] = mapped_column()
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    source_policy_version: Mapped[str] = mapped_column(String(80))
    default_preview_expiry_days: Mapped[int] = mapped_column()
    max_businesses: Mapped[int] = mapped_column()
    daily_demo_cap: Mapped[int] = mapped_column()
    daily_preview_link_cap: Mapped[int] = mapped_column()
    daily_manual_contact_cap: Mapped[int] = mapped_column()
    daily_readiness_approval_cap: Mapped[int] = mapped_column()
    created_by_operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class PilotSourcePolicyAcknowledgement(Base):
    __tablename__ = "pilot_source_policy_acknowledgements"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pilot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pilot_runs.id"), index=True)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(80))
    acknowledged_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    acknowledgement_text: Mapped[str] = mapped_column(Text)


class PilotRetrospective(Base):
    __tablename__ = "pilot_retrospectives"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pilot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pilot_runs.id"), index=True)
    created_by_operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    what_worked: Mapped[str] = mapped_column(Text, default="")
    what_failed: Mapped[str] = mapped_column(Text, default="")
    false_positives: Mapped[str] = mapped_column(Text, default="")
    false_negatives: Mapped[str] = mapped_column(Text, default="")
    operator_friction: Mapped[str] = mapped_column(Text, default="")
    demo_quality_issues: Mapped[str] = mapped_column(Text, default="")
    source_quality_issues: Mapped[str] = mapped_column(Text, default="")
    business_objections: Mapped[str] = mapped_column(Text, default="")
    reply_quality: Mapped[str] = mapped_column(Text, default="")
    meeting_quality: Mapped[str] = mapped_column(Text, default="")
    next_sprint_recommendation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class PilotExportRun(Base):
    __tablename__ = "pilot_export_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pilot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pilot_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    export_root: Mapped[str] = mapped_column(Text)
    files: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    created_by_operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (UniqueConstraint("campaign_id", "identity_key", name="uq_business_campaign_identity"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_key: Mapped[str] = mapped_column(String(300), index=True)
    source_identifier: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    normalized_phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    normalized_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(40), default="DISCOVERED", index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)


class BusinessExternalIdentity(Base):
    __tablename__ = "business_external_identities"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_external_identity_source_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    source: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[str] = mapped_column(String(300))
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    confidence: Mapped[float] = mapped_column(Float)


class BusinessAlias(Base):
    __tablename__ = "business_aliases"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    alias: Mapped[str] = mapped_column(String(300))


class SourceObservation(Base):
    __tablename__ = "source_observations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    field: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(80))
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    storage_policy: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    value: Mapped[str] = mapped_column(String(500))
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_observations.id"), nullable=True)


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    adapter_version: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class EnrichmentFactRow(Base):
    __tablename__ = "enrichment_facts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enrichment_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrichment_runs.id"), index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fact_type: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    policy: Mapped[str] = mapped_column(String(40), default="persistent")


class SuppressionEntry(Base):
    __tablename__ = "suppression_entries"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(100), default="system")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True)
    job_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class DedupeEvidence(Base):
    __tablename__ = "dedupe_evidence"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    candidate_source: Mapped[str] = mapped_column(String(80))
    candidate_source_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    matched_business_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("businesses.id"), nullable=True, index=True
    )
    discovery_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discovery_candidates.id"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(500))
    confidence: Mapped[float] = mapped_column(Float)
    merged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), index=True)
    source: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ambiguous", index=True)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    provenance: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    dedupe_evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Website(Base):
    __tablename__ = "websites"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    discovered_url: Mapped[str] = mapped_column(String(1000))
    normalized_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    final_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(40))
    checked_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class AuditRun(Base):
    __tablename__ = "audit_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    website_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("websites.id"), nullable=True, index=True)
    auditor_version: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_metadata: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class AuditFinding(Base):
    __tablename__ = "audit_findings"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_runs.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(30))
    deterministic: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(40))
    observed_value: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    auditor_version: Mapped[str] = mapped_column(String(100))


class AuditArtifact(Base):
    __tablename__ = "audit_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audit_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    audit_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audit_runs.id"), nullable=True, index=True)
    version: Mapped[str] = mapped_column(String(100))
    score: Mapped[int] = mapped_column()
    band: Mapped[str] = mapped_column(String(20))
    recommended_next_action: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OpportunityComponent(Base):
    __tablename__ = "opportunity_components"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    opportunity_score_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunity_scores.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    points: Mapped[int] = mapped_column()
    max_points: Mapped[int] = mapped_column()
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    source_type: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)


class OpportunityHold(Base):
    __tablename__ = "opportunity_holds"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    opportunity_score_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunity_scores.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class BusinessBrief(Base):
    __tablename__ = "business_briefs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    score_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity_scores.id"), nullable=True, index=True)
    audit_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audit_runs.id"), nullable=True, index=True)
    version: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    recommended_next_action: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class BusinessBriefFact(Base):
    __tablename__ = "business_brief_facts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_briefs.id"), index=True)
    fact_type: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[Any] = mapped_column(JsonType, nullable=True)
    source_type: Mapped[str] = mapped_column(String(80))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    confidence: Mapped[float] = mapped_column(Float)


class BusinessBriefOpportunity(Base):
    __tablename__ = "business_brief_opportunities"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_briefs.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class BusinessBriefRisk(Base):
    __tablename__ = "business_brief_risks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_briefs.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class GeneratedDemo(Base):
    __tablename__ = "generated_demos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_briefs.id"), index=True)
    score_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity_scores.id"), nullable=True, index=True)
    audit_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audit_runs.id"), nullable=True, index=True)
    version: Mapped[str] = mapped_column(String(100))
    demo_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), index=True)
    preview_path: Mapped[str] = mapped_column(String(1000))
    preview_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class GeneratedDemoSection(Base):
    __tablename__ = "generated_demo_sections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    section_type: Mapped[str] = mapped_column(String(50))
    heading: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column()
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class GeneratedDemoClaim(Base):
    __tablename__ = "generated_demo_claims"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(50))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    confidence: Mapped[float] = mapped_column(Float)
    approved: Mapped[bool] = mapped_column(default=False)


class DemoArtifact(Base):
    __tablename__ = "demo_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column()


class DemoQaRun(Base):
    __tablename__ = "demo_qa_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    checks: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class DemoReview(Base):
    __tablename__ = "demo_reviews"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    decision: Mapped[str] = mapped_column(String(40))
    reviewer: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    resulting_demo_status: Mapped[str] = mapped_column(String(40))
    resulting_business_state: Mapped[str] = mapped_column(String(40))


class DemoReviewChecklistItem(Base):
    __tablename__ = "demo_review_checklist_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("demo_reviews.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(300))
    passed: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutreachDraftPackage(Base):
    __tablename__ = "outreach_draft_packages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_briefs.id"), index=True)
    score_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity_scores.id"), nullable=True, index=True)
    version: Mapped[str] = mapped_column(String(100))
    offer_type: Mapped[str] = mapped_column(String(60))
    offer_angle: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OutreachDraftMessage(Base):
    __tablename__ = "outreach_draft_messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach_draft_packages.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(50))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    approved: Mapped[bool] = mapped_column(default=False)


class OutreachDraftCheck(Base):
    __tablename__ = "outreach_draft_checks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach_draft_packages.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    passed: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class OutreachReadinessReview(Base):
    __tablename__ = "outreach_readiness_reviews"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    outreach_draft_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach_draft_packages.id"), index=True)
    decision: Mapped[str] = mapped_column(String(50))
    reviewer: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    consent_basis_type: Mapped[str] = mapped_column(String(60))
    consent_basis_notes: Mapped[str] = mapped_column(Text, default="")
    resulting_business_state: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OutreachChannelApproval(Base):
    __tablename__ = "outreach_channel_approvals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    outreach_readiness_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outreach_readiness_reviews.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(30))
    outreach_draft_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("outreach_draft_messages.id"), nullable=True, index=True
    )
    approved: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutreachReadinessCheck(Base):
    __tablename__ = "outreach_readiness_checks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    outreach_readiness_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outreach_readiness_reviews.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    passed: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class OutreachExecutionRecord(Base):
    __tablename__ = "outreach_execution_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    outreach_draft_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach_draft_packages.id"), index=True)
    outreach_draft_message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach_draft_messages.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    operator: Mapped[str] = mapped_column(String(200))
    sent_at: Mapped[datetime] = mapped_column(UtcDateTime())
    external_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    resulting_business_state: Mapped[str] = mapped_column(String(40))


class LeadCrmEvent(Base):
    __tablename__ = "lead_crm_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    outreach_execution_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("outreach_execution_records.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(30))
    operator: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime())
    summary: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(40), nullable=True)
    objection_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    resulting_business_state: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ManualFollowUpTask(Base):
    __tablename__ = "manual_follow_up_tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(UtcDateTime())
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class OutreachObjection(Base):
    __tablename__ = "outreach_objections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    operator: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ProposalPackage(Base):
    __tablename__ = "proposal_packages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    score_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunity_scores.id"), nullable=True)
    audit_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audit_runs.id"), nullable=True)
    brief_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_briefs.id"), nullable=True)
    demo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generated_demos.id"), nullable=True)
    version: Mapped[str] = mapped_column(String(100))
    proposal_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(40), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ProposalSection(Base):
    __tablename__ = "proposal_sections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_packages.id"), index=True)
    section_type: Mapped[str] = mapped_column(String(60))
    heading: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column()
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class ProposalLineItem(Base):
    __tablename__ = "proposal_line_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_packages.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(default=1)
    unit: Mapped[str] = mapped_column(String(80))
    pricing_status: Mapped[str] = mapped_column(String(40))


class ProposalAssumption(Base):
    __tablename__ = "proposal_assumptions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_packages.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60))


class ProposalReviewEvent(Base):
    __tablename__ = "proposal_review_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_packages.id"), index=True)
    decision: Mapped[str] = mapped_column(String(40))
    reviewer: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    checks: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class ProposalExport(Base):
    __tablename__ = "proposal_exports"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proposal_packages.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    files: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class DeliveryProject(Base):
    __tablename__ = "delivery_projects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    proposal_package_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proposal_packages.id"), nullable=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    created_by_operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class DeliveryChecklistItem(Base):
    __tablename__ = "delivery_checklist_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_projects.id"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    code: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow, onupdate=utcnow)


class DeliveryMilestone(Base):
    __tablename__ = "delivery_milestones"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_projects.id"), index=True)
    milestone_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class DeliveryApproval(Base):
    __tablename__ = "delivery_approvals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_projects.id"), index=True)
    approval_type: Mapped[str] = mapped_column(String(80))
    approved_item: Mapped[str] = mapped_column(Text)
    operator_notes: Mapped[str] = mapped_column(Text, default="")
    client_assertion: Mapped[str] = mapped_column(Text, default="")
    artifact_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class DeliveryExport(Base):
    __tablename__ = "delivery_exports"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    delivery_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    files: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class Operator(Base):
    __tablename__ = "operators"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="operator")
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OperatorSession(Base):
    __tablename__ = "operator_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    session_hash: Mapped[str] = mapped_column(String(128), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class OperatorAssignment(Base):
    __tablename__ = "operator_assignments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"), index=True)
    assigned_by_operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="assigned")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OperatorComment(Base):
    __tablename__ = "operator_comments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"), index=True)
    comment_type: Mapped[str] = mapped_column(String(30), default="general")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class OperatorAuditEvent(Base):
    __tablename__ = "operator_audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class DemoPreviewLink(Base):
    __tablename__ = "demo_preview_links"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generated_demos.id"), index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    label: Mapped[str] = mapped_column(String(200), default="Concept preview")
    permission: Mapped[str] = mapped_column(String(30), default="external_view")
    status: Mapped[str] = mapped_column(String(30), default="active")
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_by_operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class DemoPreviewAccessEvent(Base):
    __tablename__ = "demo_preview_access_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    preview_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("demo_preview_links.id"), index=True)
    accessed_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(40))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JsonType, default=dict)


def make_engine(database_url: str) -> Any:
    kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if database_url.startswith("sqlite"):
        kwargs.update({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool})
    elif database_url.startswith("postgresql"):
        # timestamp-without-time-zone columns are converted using the session zone; pin it.
        kwargs["connect_args"] = {"options": "-c timezone=UTC"}
    return create_engine(database_url, **kwargs)


def make_session_factory(database_url: str) -> Any:
    return sessionmaker(bind=make_engine(database_url), expire_on_commit=False)
