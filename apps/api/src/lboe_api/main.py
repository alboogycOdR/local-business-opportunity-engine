"""FastAPI application for the Sprint 1 foundation."""

from __future__ import annotations

import csv
import io
import logging
import uuid
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from lboe_domain import (
    ALLOWED_TRANSITIONS,
    AuditRequest,
    BusinessBriefRequest,
    DiscoveryRequest,
    DiscoveryValidationError,
    InvalidTransition,
    LeadState,
    OpportunityScoreRequest,
    normalize_domain,
    normalize_phone,
    normalize_text,
    validate_transition,
)
from lboe_maps_scraper import MapsScraperAdapter, MapsScraperError
from lboe_website_auditor import PlaywrightAuditAdapter
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .audit_service import audit_idempotency_key, execute_audit
from .brief_service import brief_idempotency_key, execute_brief
from .config import Settings
from .db import (
    AuditArtifact,
    AuditFinding,
    AuditRun,
    Base,
    Business,
    BusinessBrief,
    BusinessBriefFact,
    BusinessBriefOpportunity,
    BusinessBriefRisk,
    BusinessExternalIdentity,
    Campaign,
    Contact,
    DemoArtifact,
    DemoQaRun,
    DiscoveryCandidate,
    GeneratedDemo,
    GeneratedDemoClaim,
    GeneratedDemoSection,
    Job,
    OpportunityComponent,
    OpportunityHold,
    OpportunityScore,
    PipelineEvent,
    SourceObservation,
    SuppressionEntry,
    Website,
    make_engine,
)
from .demo_generator import VERSION as DEMO_VERSION
from .demo_generator import qa_demo, render_demo, write_artifacts
from .discovery_service import discovery_idempotency_key, execute_discovery
from .logging import configure_logging
from .scoring_service import execute_score, score_idempotency_key

logger = logging.getLogger("lboe.api")
settings = Settings()
engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
discovery_adapter = MapsScraperAdapter(
    base_url=settings.maps_scraper_url,
    enabled=settings.maps_scraper_enabled,
    kill_switch=settings.discovery_kill_switch,
    poll_interval_seconds=settings.discovery_poll_interval_seconds,
    max_concurrency=settings.discovery_max_concurrency,
)
audit_adapter: Any = PlaywrightAuditAdapter(settings.audit_artifact_root, settings.audit_max_concurrency)


def set_discovery_adapter(adapter: Any) -> None:
    """Replace the adapter in tests/local tooling without changing route code."""
    global discovery_adapter
    discovery_adapter = adapter


def set_audit_adapter(adapter: Any) -> None:
    global audit_adapter
    audit_adapter = adapter


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    if settings.auto_create_schema:
        Base.metadata.create_all(engine)
    logger.info("api_started")
    yield


app = FastAPI(title="Local Business Opportunity Engine", version="0.1.0", lifespan=lifespan)


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    vertical: str = Field(min_length=1, max_length=100)
    geography: str | None = None
    policy: dict[str, Any] = Field(default_factory=dict)


class CampaignResponse(CampaignCreate):
    id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class ImportRequest(BaseModel):
    format: str = Field(pattern="^(json|csv)$")
    records: list[dict[str, Any]] | None = None
    csv_text: str | None = None
    source_type: str = "manual"


class TransitionRequest(BaseModel):
    to_state: LeadState
    actor: str = "operator"
    reason: str | None = None


class SuppressionRequest(BaseModel):
    reason: str = Field(min_length=1)
    channel: str | None = None


class ScoreRequestBody(BaseModel):
    idempotency_key: str | None = Field(default=None, max_length=300)


class AuditRequestBody(BaseModel):
    website_url: str | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_pages: int = Field(default=2, ge=1, le=3)
    idempotency_key: str | None = Field(default=None, max_length=300)


def db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def identity_key(record: dict[str, Any]) -> str:
    name = normalize_text(str(record.get("display_name", ""))) or ""
    locality = normalize_text(str(record.get("locality") or record.get("address_text") or "")) or ""
    return f"{name}|{locality}"[:300]


def parse_records(request: ImportRequest) -> list[dict[str, Any]]:
    if request.format == "json":
        return request.records or []
    return [dict(row) for row in csv.DictReader(io.StringIO(request.csv_text or ""))]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error: {type(exc).__name__}"
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=0.5).ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {type(exc).__name__}"
    if not all(value == "ok" for value in checks.values()):
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}


@app.post("/v1/campaigns", response_model=CampaignResponse, status_code=201)
def create_campaign(payload: CampaignCreate, session: Session = Depends(db_session)) -> Campaign:
    campaign = Campaign(**payload.model_dump())
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@app.get("/v1/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: uuid.UUID, session: Session = Depends(db_session)) -> Campaign:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    return campaign


class DiscoveryRequestBody(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=25)
    geography: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_results: int = Field(default=25, ge=1, le=100)
    timeout_seconds: float = Field(default=300, gt=0, le=3600)
    idempotency_key: str | None = Field(default=None, max_length=300)


@app.post("/v1/campaigns/{campaign_id}/discover")
async def discover_campaign(
    campaign_id: uuid.UUID,
    payload: DiscoveryRequestBody,
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    if session.get(Campaign, campaign_id) is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    request = DiscoveryRequest(campaign_id=campaign_id, **payload.model_dump())
    key = discovery_idempotency_key(request)
    existing = session.scalar(select(Job).where(Job.idempotency_key == key))
    if existing:
        return {"job_id": str(existing.id), "status": existing.status, "result": existing.payload.get("result")}
    job = Job(
        idempotency_key=key,
        job_type="DISCOVER_CAMPAIGN",
        status="running",
        payload={"request": request.model_dump(mode="json")},
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    try:
        result = await execute_discovery(session, discovery_adapter, request)
    except DiscoveryValidationError as exc:
        job.status = "failed"
        job.payload = {"request": request.model_dump(mode="json"), "error": str(exc)}
        session.commit()
        raise HTTPException(
            status_code=422, detail={"error": "invalid_discovery_request", "job_id": str(job.id)}
        ) from exc
    except MapsScraperError as exc:
        job.status = "failed"
        job.payload = {"request": request.model_dump(mode="json"), "error": str(exc)}
        session.commit()
        raise HTTPException(status_code=502, detail={"error": "discovery_failed", "job_id": str(job.id)}) from exc
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.payload = {"request": request.model_dump(mode="json"), "error": type(exc).__name__}
        session.commit()
        raise HTTPException(status_code=500, detail={"error": "discovery_failed", "job_id": str(job.id)}) from exc
    job.status = "succeeded"
    job.payload = {"request": request.model_dump(mode="json"), "result": result}
    session.commit()
    return {"job_id": str(job.id), "status": job.status, "result": result}


def business_dict(business: Business, session: Session) -> dict[str, Any]:
    observations = session.scalars(select(SourceObservation).where(SourceObservation.business_id == business.id)).all()
    contacts = session.scalars(select(Contact).where(Contact.business_id == business.id)).all()
    external_identities = session.scalars(
        select(BusinessExternalIdentity).where(BusinessExternalIdentity.business_id == business.id)
    ).all()
    return {
        "id": str(business.id),
        "campaign_id": str(business.campaign_id),
        "display_name": business.display_name,
        "category": business.category,
        "locality": business.locality,
        "address_text": business.address_text,
        "state": business.state,
        "identity_key": business.identity_key,
        "contacts": [{"channel": c.channel, "value": c.value} for c in contacts],
        "external_identities": [
            {"source": identity.source, "source_id": identity.source_id, "confidence": identity.confidence}
            for identity in external_identities
        ],
        "provenance": [
            {
                "field": o.field,
                "source_type": o.source_type,
                "source_ref": o.source_ref,
                "observed_at": o.observed_at,
                "expires_at": o.expires_at,
                "storage_policy": o.storage_policy,
                "confidence": o.confidence,
            }
            for o in observations
        ],
    }


@app.get("/v1/businesses")
def list_businesses(
    campaign_id: uuid.UUID | None = Query(default=None), session: Session = Depends(db_session)
) -> list[dict[str, Any]]:
    query = select(Business).order_by(Business.created_at)
    if campaign_id:
        query = query.where(Business.campaign_id == campaign_id)
    return [business_dict(item, session) for item in session.scalars(query).all()]


@app.get("/v1/businesses/{business_id}")
def get_business(business_id: uuid.UUID, session: Session = Depends(db_session)) -> dict[str, Any]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    return business_dict(business, session)


def audit_dict(run: AuditRun, session: Session) -> dict[str, Any]:
    website = session.get(Website, run.website_id) if run.website_id else None
    findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_run_id == run.id)).all()
    artifacts = session.scalars(select(AuditArtifact).where(AuditArtifact.audit_run_id == run.id)).all()
    return {
        "id": str(run.id),
        "business_id": str(run.business_id),
        "website_id": str(run.website_id) if run.website_id else None,
        "auditor_version": run.auditor_version,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_summary": run.error_summary,
        "website": {
            "discovered_url": website.discovered_url,
            "normalized_url": website.normalized_url,
            "final_url": website.final_url,
            "http_status": website.http_status,
            "resolution_status": website.resolution_status,
            "checked_at": website.checked_at,
        }
        if website
        else None,
        "findings": [
            {
                "code": f.code,
                "category": f.category,
                "severity": f.severity,
                "deterministic": f.deterministic,
                "status": f.status,
                "observed_value": f.observed_value,
                "evidence": f.evidence,
                "source_url": f.source_url,
                "observed_at": f.observed_at,
                "confidence": f.confidence,
                "auditor_version": f.auditor_version,
            }
            for f in findings
        ],
        "artifacts": [
            {"kind": a.kind, "path": a.path, "mime_type": a.mime_type, "byte_size": a.byte_size} for a in artifacts
        ],
        "technical_metadata": run.technical_metadata,
    }


@app.post("/v1/businesses/{business_id}/audit")
async def audit_business(
    business_id: uuid.UUID, payload: AuditRequestBody, session: Session = Depends(db_session)
) -> dict[str, Any]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    website_url = payload.website_url
    if website_url is None:
        website_contact = session.scalar(
            select(Contact).where(Contact.business_id == business.id, Contact.channel == "website")
        )
        website_url = website_contact.value if website_contact else None
    request = AuditRequest(
        business_id=business_id,
        website_url=website_url,
        timeout_seconds=payload.timeout_seconds,
        max_pages=payload.max_pages,
        idempotency_key=payload.idempotency_key,
    )
    key = audit_idempotency_key(request)
    existing = session.scalar(select(Job).where(Job.idempotency_key == key))
    if existing and existing.payload.get("audit_run_id"):
        run = session.get(AuditRun, uuid.UUID(str(existing.payload["audit_run_id"])))
        if run:
            return audit_dict(run, session)
    job = Job(
        idempotency_key=key, job_type="AUDIT_WEBSITE", status="running", payload={"business_id": str(business_id)}
    )
    session.add(job)
    session.commit()
    try:
        run, _result = await execute_audit(session, audit_adapter, business, request)
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.payload = {"business_id": str(business_id), "error": type(exc).__name__}
        session.commit()
        raise HTTPException(status_code=502, detail={"error": "audit_failed", "job_id": str(job.id)}) from exc
    job.status = "succeeded"
    job.payload = {"business_id": str(business_id), "audit_run_id": str(run.id)}
    session.commit()
    return audit_dict(run, session)


@app.get("/v1/businesses/{business_id}/audits")
def list_audits(business_id: uuid.UUID, session: Session = Depends(db_session)) -> list[dict[str, Any]]:
    if session.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    return [
        audit_dict(run, session)
        for run in session.scalars(
            select(AuditRun).where(AuditRun.business_id == business_id).order_by(AuditRun.started_at)
        ).all()
    ]


@app.get("/v1/audits/{audit_id}")
def get_audit(audit_id: uuid.UUID, session: Session = Depends(db_session)) -> dict[str, Any]:
    run = session.get(AuditRun, audit_id)
    if run is None:
        raise HTTPException(status_code=404, detail="audit_not_found")
    return audit_dict(run, session)


def score_dict(score: OpportunityScore, session: Session) -> dict[str, Any]:
    components = session.scalars(
        select(OpportunityComponent).where(OpportunityComponent.opportunity_score_id == score.id)
    ).all()
    holds = session.scalars(select(OpportunityHold).where(OpportunityHold.opportunity_score_id == score.id)).all()
    return {
        "id": str(score.id),
        "business_id": str(score.business_id),
        "audit_run_id": str(score.audit_run_id) if score.audit_run_id else None,
        "score": score.score,
        "band": score.band,
        "version": score.version,
        "recommended_next_action": score.recommended_next_action,
        "created_at": score.created_at,
        "components": [
            {
                "code": item.code,
                "category": item.category,
                "points": item.points,
                "max_points": item.max_points,
                "evidence": item.evidence,
                "source_type": item.source_type,
                "confidence": item.confidence,
            }
            for item in components
        ],
        "holds": [
            {"code": item.code, "reason": item.reason, "severity": item.severity, "evidence": item.evidence}
            for item in holds
        ],
    }


@app.post("/v1/businesses/{business_id}/score")
async def score_business(
    business_id: uuid.UUID,
    payload: ScoreRequestBody | None = None,
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    if session.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    request = OpportunityScoreRequest(
        business_id=business_id,
        idempotency_key=payload.idempotency_key if payload else None,
    )
    key = score_idempotency_key(request)
    existing = session.scalar(select(Job).where(Job.idempotency_key == key))
    if existing and existing.payload.get("score_id"):
        score = session.get(OpportunityScore, uuid.UUID(str(existing.payload["score_id"])))
        if score:
            return score_dict(score, session)
    job = Job(
        idempotency_key=key,
        job_type="CALCULATE_SCORE",
        status="running",
        payload={"business_id": str(business_id)},
    )
    session.add(job)
    session.commit()
    business = session.get(Business, business_id)
    assert business is not None
    try:
        score, _result = await execute_score(session, request, business)
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.payload = {"business_id": str(business_id), "error": type(exc).__name__}
        session.commit()
        raise HTTPException(status_code=500, detail={"error": "score_failed", "job_id": str(job.id)}) from exc
    job.status = "succeeded"
    job.payload = {"business_id": str(business_id), "score_id": str(score.id)}
    session.commit()
    return score_dict(score, session)


@app.get("/v1/businesses/{business_id}/scores")
def list_scores(business_id: uuid.UUID, session: Session = Depends(db_session)) -> list[dict[str, Any]]:
    if session.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    scores = session.scalars(
        select(OpportunityScore)
        .where(OpportunityScore.business_id == business_id)
        .order_by(OpportunityScore.created_at)
    ).all()
    return [score_dict(item, session) for item in scores]


@app.get("/v1/scores/{score_id}")
def get_score(score_id: uuid.UUID, session: Session = Depends(db_session)) -> dict[str, Any]:
    score = session.get(OpportunityScore, score_id)
    if score is None:
        raise HTTPException(status_code=404, detail="score_not_found")
    return score_dict(score, session)


def brief_dict(brief: BusinessBrief, session: Session) -> dict[str, Any]:
    facts = session.scalars(select(BusinessBriefFact).where(BusinessBriefFact.business_brief_id == brief.id)).all()
    opportunities = session.scalars(
        select(BusinessBriefOpportunity).where(BusinessBriefOpportunity.business_brief_id == brief.id)
    ).all()
    risks = session.scalars(select(BusinessBriefRisk).where(BusinessBriefRisk.business_brief_id == brief.id)).all()
    action_text = {
        "score_only": ("Score only", "No immediate demo recommended. Review for light technical cleanup or archive."),
        "technical_cleanup_offer": (
            "Technical cleanup review",
            "Consider a technical cleanup, accessibility, or SEO hygiene offer.",
        ),
        "conversion_upgrade_offer": ("Conversion upgrade review", "Consider a conversion upgrade concept."),
        "generate_demo": ("Concept demo eligible", "Eligible for concept demo generation."),
        "manual_review": ("Manual review required", "Manual review required before any next step."),
        "do_not_contact": ("Do not contact", "Do not contact; suppression or policy hold applies."),
        "audit_required": ("Audit required", "Audit required before recommendation."),
        "archive": ("Archive", "Archive unless new verified evidence becomes available."),
    }
    code = brief.recommended_next_action
    label, rationale = action_text.get(code, (code, code))
    by_type: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        by_type.setdefault(fact.fact_type, []).append(
            {
                "label": fact.label,
                "value": fact.value,
                "source_type": fact.source_type,
                "evidence": fact.evidence,
                "confidence": fact.confidence,
            }
        )
    return {
        "id": str(brief.id),
        "business_id": str(brief.business_id),
        "score_id": str(brief.score_id) if brief.score_id else None,
        "audit_run_id": str(brief.audit_run_id) if brief.audit_run_id else None,
        "version": brief.version,
        "summary": brief.summary,
        "recommended_action": {"code": code, "label": label, "rationale": rationale},
        "confidence": brief.confidence,
        "created_at": brief.created_at,
        "facts": by_type,
        "opportunities": [
            {
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "priority": item.priority,
                "evidence": item.evidence,
            }
            for item in opportunities
        ],
        "risks": [
            {
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "severity": item.severity,
                "evidence": item.evidence,
            }
            for item in risks
        ],
    }


@app.post("/v1/businesses/{business_id}/brief")
async def create_brief(
    business_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    request = BusinessBriefRequest(business_id=business_id, idempotency_key=(payload or {}).get("idempotency_key"))
    key = brief_idempotency_key(request)
    existing = session.scalar(select(Job).where(Job.idempotency_key == key))
    if existing and existing.payload.get("brief_id"):
        brief = session.get(BusinessBrief, uuid.UUID(str(existing.payload["brief_id"])))
        if brief:
            return brief_dict(brief, session)
    job = Job(
        job_type="GENERATE_BRIEF", idempotency_key=key, status="running", payload={"business_id": str(business_id)}
    )
    session.add(job)
    session.commit()
    try:
        brief, _result = await execute_brief(session, request, business)
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.payload = {"business_id": str(business_id), "error": type(exc).__name__}
        session.commit()
        raise HTTPException(status_code=500, detail={"error": "brief_failed", "job_id": str(job.id)}) from exc
    job.status = "succeeded"
    job.payload = {"business_id": str(business_id), "brief_id": str(brief.id)}
    session.commit()
    return brief_dict(brief, session)


@app.get("/v1/businesses/{business_id}/briefs")
def list_briefs(business_id: uuid.UUID, session: Session = Depends(db_session)) -> list[dict[str, Any]]:
    if session.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    briefs = session.scalars(
        select(BusinessBrief).where(BusinessBrief.business_id == business_id).order_by(BusinessBrief.created_at)
    ).all()
    return [brief_dict(item, session) for item in briefs]


@app.get("/v1/briefs/{brief_id}")
def get_brief(brief_id: uuid.UUID, session: Session = Depends(db_session)) -> dict[str, Any]:
    brief = session.get(BusinessBrief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief_not_found")
    return brief_dict(brief, session)


def demo_dict(demo: GeneratedDemo, session: Session) -> dict[str, Any]:
    sections = session.scalars(
        select(GeneratedDemoSection)
        .where(GeneratedDemoSection.demo_id == demo.id)
        .order_by(GeneratedDemoSection.sort_order)
    ).all()
    claims = session.scalars(select(GeneratedDemoClaim).where(GeneratedDemoClaim.demo_id == demo.id)).all()
    artifacts = session.scalars(select(DemoArtifact).where(DemoArtifact.demo_id == demo.id)).all()
    qa = session.scalar(select(DemoQaRun).where(DemoQaRun.demo_id == demo.id).order_by(DemoQaRun.created_at.desc()))
    return {
        "id": str(demo.id),
        "business_id": str(demo.business_id),
        "brief_id": str(demo.brief_id),
        "score_id": str(demo.score_id) if demo.score_id else None,
        "audit_run_id": str(demo.audit_run_id) if demo.audit_run_id else None,
        "version": demo.version,
        "demo_type": demo.demo_type,
        "status": demo.status,
        "preview_path": demo.preview_path,
        "preview_url": demo.preview_url,
        "created_at": demo.created_at,
        "sections": [
            {
                "section_type": x.section_type,
                "heading": x.heading,
                "body": x.body,
                "sort_order": x.sort_order,
                "evidence": x.evidence,
            }
            for x in sections
        ],
        "claims": [
            {
                "claim_text": x.claim_text,
                "claim_type": x.claim_type,
                "evidence": x.evidence,
                "confidence": x.confidence,
                "approved": x.approved,
            }
            for x in claims
        ],
        "artifacts": [
            {"kind": x.kind, "path": x.path, "mime_type": x.mime_type, "byte_size": x.byte_size} for x in artifacts
        ],
        "qa": {"status": qa.status, "checks": qa.checks, "created_at": qa.created_at} if qa else None,
    }


@app.post("/v1/businesses/{business_id}/demo")
def create_demo(
    business_id: uuid.UUID, payload: dict[str, Any] | None = None, session: Session = Depends(db_session)
) -> dict[str, Any]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    latest_brief = session.scalar(
        select(BusinessBrief).where(BusinessBrief.business_id == business_id).order_by(BusinessBrief.created_at.desc())
    )
    if latest_brief is None:
        return {"status": "not_demo_eligible", "reason": "brief_required", "business_id": str(business_id)}
    body = payload or {}
    brief = brief_dict(latest_brief, session)
    action = latest_brief.recommended_next_action
    fact_labels = {fact["label"] for values in brief.get("facts", {}).values() for fact in values}
    if business.state == LeadState.SUPPRESSED.value:
        action = "do_not_contact"
    if any(risk.get("code") == "AMBIGUOUS_IDENTITY" for risk in brief.get("risks", [])):
        action = "manual_review"
    if action in {"generate_demo", "conversion_upgrade_offer", "technical_cleanup_offer"} and (
        "Business name" not in fact_labels or "Category" not in fact_labels
    ):
        action = "insufficient_facts"
    blocked_reasons = {
        "score_only": "score_only",
        "manual_review": "ambiguous_identity",
        "do_not_contact": "do_not_contact",
        "audit_required": "audit_required",
        "archive": "archive",
        "insufficient_facts": "insufficient_facts",
    }
    reason = blocked_reasons.get(action)
    if reason is not None:
        key = f"GENERATE_DEMO:{business_id}:{latest_brief.id}:{body.get('idempotency_key', 'default')}"
        existing = session.scalar(select(Job).where(Job.idempotency_key == key))
        if existing:
            return {
                "status": "not_demo_eligible",
                "reason": reason,
                "business_id": str(business_id),
                "job_id": str(existing.id),
            }
        job = Job(
            job_type="GENERATE_DEMO",
            idempotency_key=key,
            status="not_eligible",
            payload={"business_id": str(business_id), "reason": reason},
        )
        session.add(job)
        session.commit()
        return {"status": "not_demo_eligible", "reason": reason, "business_id": str(business_id), "job_id": str(job.id)}
    demo_type = body.get("demo_type") or (
        "conversion_upgrade"
        if action == "conversion_upgrade_offer"
        else "technical_cleanup_preview"
        if action == "technical_cleanup_offer"
        else "starter_website"
    )
    key = f"GENERATE_DEMO:{business_id}:{latest_brief.id}:{demo_type}:{body.get('idempotency_key', 'default')}"
    existing = session.scalar(select(Job).where(Job.idempotency_key == key))
    if existing and existing.payload.get("demo_id"):
        demo = session.get(GeneratedDemo, uuid.UUID(str(existing.payload["demo_id"])))
        if demo:
            return demo_dict(demo, session)
    job = Job(
        job_type="GENERATE_DEMO", idempotency_key=key, status="running", payload={"business_id": str(business_id)}
    )
    session.add(job)
    session.commit()
    demo = GeneratedDemo(
        business_id=business_id,
        brief_id=latest_brief.id,
        score_id=latest_brief.score_id,
        audit_run_id=latest_brief.audit_run_id,
        version=DEMO_VERSION,
        demo_type=demo_type,
        status="rendering",
        preview_path="",
    )
    session.add(demo)
    session.commit()
    try:
        rendered = render_demo(demo.id, business, brief, demo_type)
        artifact_root = __import__("pathlib").Path(settings.demo_artifact_root)
        artifact_rows = write_artifacts(artifact_root, demo.id, rendered)
        qa_status, checks = qa_demo(artifact_root, demo.id, rendered)
        demo.preview_path = str(artifact_root / "demos" / str(demo.id) / "index.html")
        demo.status = "qa_passed" if qa_status == "passed" else "qa_failed"
        for section in rendered.sections:
            session.add(
                GeneratedDemoSection(
                    demo_id=demo.id,
                    section_type=section.section_type,
                    heading=section.heading,
                    body=section.body,
                    sort_order=section.sort_order,
                    evidence=section.evidence,
                )
            )
        for claim in rendered.claims:
            session.add(
                GeneratedDemoClaim(
                    demo_id=demo.id,
                    claim_text=claim.claim_text,
                    claim_type=claim.claim_type,
                    evidence=claim.evidence,
                    confidence=claim.confidence,
                    approved=claim.approved,
                )
            )
        for item in artifact_rows:
            session.add(DemoArtifact(demo_id=demo.id, **item))
        session.add(DemoQaRun(demo_id=demo.id, status=qa_status, checks=checks))
        if qa_status == "passed":
            current = LeadState(business.state)
            if current == LeadState.SCORED:
                for target in (LeadState.DEMO_QUEUED, LeadState.DEMO_GENERATED, LeadState.REVIEW_PENDING):
                    validate_transition(current, target)
                    session.add(
                        PipelineEvent(
                            business_id=business.id,
                            from_state=current.value,
                            to_state=target.value,
                            actor="system",
                            reason="concept demo generated and QA passed",
                        )
                    )
                    current = target
                    business.state = target.value
        job.status = "succeeded" if qa_status == "passed" else "failed"
        job.payload = {"business_id": str(business_id), "demo_id": str(demo.id), "qa_status": qa_status}
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        failed_job = session.get(Job, job.id)
        if failed_job:
            failed_job.status = "failed"
            failed_job.payload = {"business_id": str(business_id), "error": type(exc).__name__}
            session.commit()
        raise HTTPException(
            status_code=500, detail={"error": "demo_failed", "job_id": str(failed_job.id) if failed_job else None}
        ) from exc
    return demo_dict(demo, session)


@app.get("/v1/businesses/{business_id}/demos")
def list_demos(business_id: uuid.UUID, session: Session = Depends(db_session)) -> list[dict[str, Any]]:
    if session.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    return [
        demo_dict(item, session)
        for item in session.scalars(
            select(GeneratedDemo).where(GeneratedDemo.business_id == business_id).order_by(GeneratedDemo.created_at)
        ).all()
    ]


@app.get("/v1/demos/{demo_id}")
def get_demo(demo_id: uuid.UUID, session: Session = Depends(db_session)) -> dict[str, Any]:
    demo = session.get(GeneratedDemo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="demo_not_found")
    return demo_dict(demo, session)


@app.get("/v1/campaigns/{campaign_id}/discovery-candidates")
def list_discovery_candidates(
    campaign_id: uuid.UUID,
    candidate_status: str | None = Query(default=None, alias="status"),
    session: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    query = select(DiscoveryCandidate).where(DiscoveryCandidate.campaign_id == campaign_id)
    if candidate_status:
        query = query.where(DiscoveryCandidate.status == candidate_status)
    return [
        {
            "id": str(candidate.id),
            "source": candidate.source,
            "source_id": candidate.source_id,
            "status": candidate.status,
            "normalized_payload": candidate.normalized_payload,
            "provenance": candidate.provenance,
            "dedupe_evidence": candidate.dedupe_evidence,
            "created_at": candidate.created_at,
        }
        for candidate in session.scalars(query.order_by(DiscoveryCandidate.created_at)).all()
    ]


@app.post("/v1/campaigns/{campaign_id}/import")
def import_candidates(
    campaign_id: uuid.UUID, request: ImportRequest, session: Session = Depends(db_session)
) -> dict[str, Any]:
    if session.get(Campaign, campaign_id) is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, row in enumerate(parse_records(request), start=1):
        name = str(row.get("display_name", "")).strip()
        if not name:
            failures.append({"row": index, "error": "display_name_required"})
            continue
        key = identity_key(row)
        existing = session.scalar(
            select(Business).where(Business.campaign_id == campaign_id, Business.identity_key == key)
        )
        if existing:
            failures.append({"row": index, "error": "exact_duplicate", "business_id": str(existing.id)})
            continue
        business = Business(
            campaign_id=campaign_id,
            display_name=name,
            category=row.get("category"),
            locality=row.get("locality"),
            address_text=row.get("address_text"),
            identity_key=key,
            normalized_phone=normalize_phone(row.get("phone")),
            normalized_domain=normalize_domain(row.get("website")),
        )
        session.add(business)
        session.flush()
        observed_at = datetime.now(UTC)
        common = {
            "business_id": business.id,
            "source_type": request.source_type,
            "source_ref": row.get("source_ref") or row.get("source_url"),
            "observed_at": observed_at,
            "storage_policy": "persistent",
            "confidence": 0.9,
        }
        session.add(SourceObservation(field="identity.display_name", value=name, **common))
        for field, value in (
            ("identity.category", row.get("category")),
            ("identity.locality", row.get("locality")),
            ("identity.address_text", row.get("address_text")),
        ):
            if value:
                session.add(SourceObservation(field=field, value=str(value), **common))
        for channel in ("phone", "website"):
            value = row.get(channel)
            if value:
                observation = SourceObservation(field=f"contact.{channel}", value=str(value), **common)
                session.add(observation)
                session.flush()
                session.add(
                    Contact(
                        business_id=business.id, channel=channel, value=str(value), source_observation_id=observation.id
                    )
                )
        session.add(
            PipelineEvent(
                business_id=business.id,
                from_state=None,
                to_state=LeadState.DISCOVERED.value,
                actor="import",
                reason="manual_import",
            )
        )
        successes.append({"row": index, "business_id": str(business.id)})
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="duplicate_business") from None
    return {"imported": len(successes), "failed": len(failures), "successes": successes, "failures": failures}


@app.post("/v1/businesses/{business_id}/transition")
def transition_business(
    business_id: uuid.UUID, request: TransitionRequest, session: Session = Depends(db_session)
) -> dict[str, Any]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    current = LeadState(business.state)
    try:
        validate_transition(current, request.to_state)
    except (InvalidTransition, ValueError) as exc:
        raise HTTPException(status_code=409, detail={"error": "invalid_transition", "message": str(exc)}) from exc
    business.state = request.to_state.value
    session.add(
        PipelineEvent(
            business_id=business.id,
            from_state=current.value,
            to_state=request.to_state.value,
            actor=request.actor,
            reason=request.reason,
        )
    )
    session.commit()
    return {"business_id": str(business.id), "state": business.state}


@app.post("/v1/businesses/{business_id}/suppressions", status_code=201)
def suppress_business(
    business_id: uuid.UUID, request: SuppressionRequest, session: Session = Depends(db_session)
) -> dict[str, Any]:
    business = session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    entry = SuppressionEntry(business_id=business.id, reason=request.reason, channel=request.channel)
    session.add(entry)
    current = LeadState(business.state)
    if current != LeadState.SUPPRESSED and LeadState.SUPPRESSED in ALLOWED_TRANSITIONS.get(current, frozenset()):
        business.state = LeadState.SUPPRESSED.value
        session.add(
            PipelineEvent(
                business_id=business.id,
                from_state=current.value,
                to_state=LeadState.SUPPRESSED.value,
                actor="operator",
                reason=request.reason,
            )
        )
    session.commit()
    return {"id": str(entry.id), "business_id": str(business.id), "reason": entry.reason, "channel": entry.channel}


@app.get("/v1/businesses/{business_id}/suppressions")
def list_suppressions(business_id: uuid.UUID, session: Session = Depends(db_session)) -> list[dict[str, Any]]:
    if session.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    return [
        {"id": str(item.id), "reason": item.reason, "channel": item.channel, "created_at": item.created_at}
        for item in session.scalars(select(SuppressionEntry).where(SuppressionEntry.business_id == business_id)).all()
    ]
