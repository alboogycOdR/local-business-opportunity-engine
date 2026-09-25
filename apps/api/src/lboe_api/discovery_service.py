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

from .db import Business, Contact, DedupeEvidence, PipelineEvent, SourceObservation


def discovery_idempotency_key(request: DiscoveryRequest) -> str:
    material = request.idempotency_key or json.dumps(
        {
            "campaign_id": str(request.campaign_id),
            "queries": request.queries,
            "geography": request.geography,
            "max_results": request.max_results,
        },
        sort_keys=True,
    )
    return "discover:" + hashlib.sha256(material.encode()).hexdigest()


def _existing_by_signal(session: Session, campaign_id: UUID, candidate: CandidateBusiness) -> dict[str, list[Business]]:
    signals = identity_signals(candidate)
    candidates = session.scalars(select(Business).where(Business.campaign_id == campaign_id)).all()
    matches: defaultdict[str, list[Business]] = defaultdict(list)
    for business in candidates:
        if signals.source_id and business.source_identifier == f"{candidate.source}:{signals.source_id}":
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


def persist_candidate(
    session: Session, campaign_id: UUID, candidate: CandidateBusiness
) -> tuple[Business | None, str, bool]:
    """Persist a candidate or evidence of a conservative non-merge decision."""
    signals = identity_signals(candidate)
    matches = _existing_by_signal(session, campaign_id, candidate)
    matched_ids = {business.id for values in matches.values() for business in values}
    if len(matched_ids) > 1:
        reason = "multiple identity signals point to different businesses; manual review required"
        session.add(
            DedupeEvidence(
                campaign_id=campaign_id,
                candidate_source=candidate.source,
                candidate_source_id=signals.source_id,
                method="ambiguous",
                reason=reason,
                confidence=0.0,
                merged=False,
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
        source_identifier=f"{candidate.source}:{signals.source_id}" if signals.source_id else None,
        normalized_phone=signals.phone,
        normalized_domain=signals.domain,
    )
    session.add(business)
    session.flush()
    _record_candidate_facts(session, business, candidate)
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
