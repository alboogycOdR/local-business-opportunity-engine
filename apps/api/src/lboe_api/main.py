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
    DiscoveryRequest,
    InvalidTransition,
    LeadState,
    normalize_domain,
    normalize_phone,
    normalize_text,
    validate_transition,
)
from lboe_maps_scraper import MapsScraperAdapter, MapsScraperError
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .db import (
    Base,
    Business,
    Campaign,
    Contact,
    Job,
    PipelineEvent,
    SourceObservation,
    SuppressionEntry,
    make_engine,
)
from .discovery_service import discovery_idempotency_key, execute_discovery
from .logging import configure_logging

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


def set_discovery_adapter(adapter: Any) -> None:
    """Replace the adapter in tests/local tooling without changing route code."""
    global discovery_adapter
    discovery_adapter = adapter


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
