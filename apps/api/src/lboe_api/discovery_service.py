"""Discovery orchestration: adapter invocation, normalization, dedupe, and persistence."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from lboe_domain import CandidateBusiness, DiscoveryAdapter, DiscoveryRequest, identity_signals
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import (
    Business,
    BusinessExternalIdentity,
    Contact,
    DedupeEvidence,
    DiscoveryCandidate,
    PipelineEvent,
    SourceObservation,
)


def discovery_idempotency_key(request: DiscoveryRequest) -> str:
    material = {
        "campaign_id": str(request.campaign_id),
        "caller_key": request.idempotency_key,
        "queries": sorted(" ".join(query.casefold().split()) for query in request.queries),
        "geography": " ".join(request.geography.casefold().split()) if request.geography else None,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "max_results": request.max_results,
        "timeout_seconds": request.timeout_seconds,
    }
    material_json = json.dumps(material, sort_keys=True)
    return "discover:" + hashlib.sha256(material_json.encode()).hexdigest()


def _existing_by_signal(session: Session, campaign_id: UUID, candidate: CandidateBusiness) -> dict[str, list[Business]]:
    signals = identity_signals(candidate)
    candidates = session.scalars(select(Business).where(Business.campaign_id == campaign_id)).all()
    external_rows = session.execute(
        select(BusinessExternalIdentity, Business)
        .join(Business, Business.id == BusinessExternalIdentity.business_id)
        .where(Business.campaign_id == campaign_id)
    ).all()
    external_by_key = {(identity.source, identity.source_id): business for identity, business in external_rows}
    matches: defaultdict[str, list[Business]] = defaultdict(list)
    for business in candidates:
        if signals.source_id and external_by_key.get((candidate.source, signals.source_id)) == business:
            matches["source_id"].append(business)
        if signals.phone and business.normalized_phone == signals.phone:
            matches["phone"].append(business)
        if signals.domain and business.normalized_domain == signals.domain:
            matches["domain"].append(business)
        if signals.name_locality == business.identity_key:
            matches["name_locality"].append(business)
    return dict(matches)


def _record_candidate_facts(session: Session, business: Business, candidate: CandidateBusiness) -> None:
    common: dict[str, Any] = {
        "business_id": business.id,
        "source_type": candidate.source,
        "source_ref": candidate.source_url or candidate.provenance.get("source_ref"),
        "observed_at": candidate.observed_at,
        "storage_policy": candidate.provenance.get("storage_policy", "persistent"),
        "confidence": candidate.confidence,
    }
    facts = {
        "identity.display_name": candidate.display_name,
        "identity.category": candidate.category,
        "identity.locality": candidate.locality,
        "identity.address_text": candidate.address_text,
        "contact.phone": candidate.phone,
        "contact.website": candidate.website,
        "identity.external_id": candidate.source_id,
    }
    for field, value in facts.items():
        if value:
            observation = SourceObservation(field=field, value=str(value), **common)
            session.add(observation)
            if field == "contact.phone":
                session.flush()
                session.add(
                    Contact(
                        business_id=business.id,
                        channel="phone",
                        value=str(value),
                        source_observation_id=observation.id,
                    )
                )
            elif field == "contact.website":
                session.flush()
                session.add(
                    Contact(
                        business_id=business.id,
                        channel="website",
                        value=str(value),
                        source_observation_id=observation.id,
                    )
                )


def _attach_external_identity(session: Session, business: Business, candidate: CandidateBusiness) -> None:
    if not candidate.source_id:
        return
    identity = session.scalar(
        select(BusinessExternalIdentity).where(
            BusinessExternalIdentity.source == candidate.source,
            BusinessExternalIdentity.source_id == candidate.source_id,
        )
    )
    if identity is None:
        session.add(
            BusinessExternalIdentity(
                business_id=business.id,
                source=candidate.source,
                source_id=candidate.source_id,
                observed_at=candidate.observed_at,
                confidence=candidate.confidence,
            )
        )
    elif identity.business_id == business.id:
        identity.observed_at = candidate.observed_at
        identity.confidence = max(identity.confidence, candidate.confidence)


def persist_candidate(
    session: Session, campaign_id: UUID, candidate: CandidateBusiness
) -> tuple[Business | None, str, bool]:
    """Persist a candidate or evidence of a conservative non-merge decision."""
    signals = identity_signals(candidate)
    matches = _existing_by_signal(session, campaign_id, candidate)
    matched_ids = {business.id for values in matches.values() for business in values}
    if len(matched_ids) > 1:
        reason = "multiple identity signals point to different businesses; manual review required"
        conflict_ids = [str(business_id) for business_id in sorted(matched_ids, key=str)]
        candidate_record = DiscoveryCandidate(
            campaign_id=campaign_id,
            source=candidate.source,
            source_id=signals.source_id,
            status="ambiguous",
            normalized_payload=candidate.model_dump(mode="json"),
            provenance=candidate.provenance,
            dedupe_evidence={"conflicting_business_ids": conflict_ids, "signals": list(matches)},
        )
        session.add(candidate_record)
        session.flush()
        session.add(
            DedupeEvidence(
                campaign_id=campaign_id,
                candidate_source=candidate.source,
                candidate_source_id=signals.source_id,
                method="ambiguous",
                reason=reason,
                confidence=0.0,
                merged=False,
                discovery_candidate_id=candidate_record.id,
            )
        )
        return None, "ambiguous", False
    if len(matched_ids) == 1:
        business_id = next(iter(matched_ids))
        business = session.get(Business, business_id)
        assert business is not None
        methods = [method for method, values in matches.items() if values]
        method = methods[0] if methods else "unknown"
        reason = f"conservative exact match on {', '.join(methods)}"
        _record_candidate_facts(session, business, candidate)
        _attach_external_identity(session, business, candidate)
        session.add(
            DedupeEvidence(
                campaign_id=campaign_id,
                candidate_source=candidate.source,
                candidate_source_id=signals.source_id,
                matched_business_id=business.id,
                method=method,
                reason=reason,
                confidence=1.0,
                merged=True,
            )
        )
        return business, method, True

    identity_key = signals.name_locality[:300]
    business = Business(
        campaign_id=campaign_id,
        display_name=candidate.display_name,
        category=candidate.category,
        locality=candidate.locality,
        address_text=candidate.address_text,
        identity_key=identity_key,
        normalized_phone=signals.phone,
        normalized_domain=signals.domain,
    )
    session.add(business)
    session.flush()
    _record_candidate_facts(session, business, candidate)
    _attach_external_identity(session, business, candidate)
    session.add(
        PipelineEvent(
            business_id=business.id, from_state=None, to_state="DISCOVERED", actor="discovery", reason=candidate.source
        )
    )
    session.add(
        DedupeEvidence(
            campaign_id=campaign_id,
            candidate_source=candidate.source,
            candidate_source_id=signals.source_id,
            matched_business_id=business.id,
            method="none",
            reason="no conservative duplicate match",
            confidence=1.0,
            merged=False,
        )
    )
    return business, "new", False


async def execute_discovery(session: Session, adapter: DiscoveryAdapter, request: DiscoveryRequest) -> dict[str, Any]:
    candidates = await adapter.discover(request)
    imported = 0
    duplicates = 0
    ambiguous = 0
    for candidate in candidates:
        business, method, merged = persist_candidate(session, request.campaign_id, candidate)
        if method == "ambiguous":
            ambiguous += 1
        elif merged:
            duplicates += 1
        else:
            imported += 1
    session.commit()
    return {"candidates": len(candidates), "imported": imported, "duplicates": duplicates, "ambiguous": ambiguous}
