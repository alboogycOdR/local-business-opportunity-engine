"""Score orchestration, evidence projection, and durable score history."""

from __future__ import annotations

import hashlib
import json

from lboe_domain import (
    AuditEvidence,
    AuditFinding,
    LeadState,
    OpportunityScoreRequest,
    OpportunityScoreResult,
    validate_transition,
)
from lboe_scoring import ScoreContext, score_opportunity
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import (
    AuditFinding as AuditFindingRow,
)
from .db import (
    AuditRun,
    Business,
    Contact,
    DiscoveryCandidate,
    OpportunityComponent,
    OpportunityHold,
    OpportunityScore,
    PipelineEvent,
    SuppressionEntry,
)


def score_idempotency_key(request: OpportunityScoreRequest) -> str:
    material = {
        "business_id": str(request.business_id),
        "caller_key": request.idempotency_key,
        "version": "opportunity-v1",
    }
    return "score:" + hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _latest_context(session: Session, business: Business) -> tuple[ScoreContext, AuditRun | None]:
    audit = session.scalar(
        select(AuditRun).where(AuditRun.business_id == business.id).order_by(AuditRun.completed_at.desc())
    )
    rows = (
        session.scalars(select(AuditFindingRow).where(AuditFindingRow.audit_run_id == audit.id)).all() if audit else []
    )
    findings = [
        AuditFinding(
            code=row.code,
            category=row.category,
            severity=row.severity,
            deterministic=row.deterministic,
            status=row.status,
            observed_value=(row.observed_value or {}).get("value")
            if isinstance(row.observed_value, dict) and set(row.observed_value) == {"value"}
            else row.observed_value,
            evidence=[AuditEvidence(kind="persisted", value=row.evidence)],
            source_url=row.source_url,
            observed_at=row.observed_at,
            confidence=row.confidence,
            auditor_version=row.auditor_version,
        )
        for row in rows
    ]
    contacts = session.scalars(select(Contact).where(Contact.business_id == business.id)).all()
    website = next((item.value for item in contacts if item.channel == "website"), None)
    phone = next((item.value for item in contacts if item.channel == "phone"), None)
    suppressed = (
        session.scalar(select(SuppressionEntry.id).where(SuppressionEntry.business_id == business.id)) is not None
    )
    ambiguous = any(
        candidate.normalized_payload.get("display_name") == business.display_name
        for candidate in session.scalars(
            select(DiscoveryCandidate).where(
                DiscoveryCandidate.campaign_id == business.campaign_id,
                DiscoveryCandidate.status == "ambiguous",
            )
        ).all()
    )
    context = ScoreContext(
        business_id=business.id,
        display_name=business.display_name,
        category=business.category,
        address_text=business.address_text,
        website_url=website,
        phone=phone,
        state=business.state,
        audit_findings=findings,
        suppressed=suppressed,
        ambiguous=ambiguous,
        source_count=len(contacts),
    )
    return context, audit


def persist_score(
    session: Session, business: Business, result: OpportunityScoreResult, audit: AuditRun | None
) -> OpportunityScore:
    row = OpportunityScore(
        business_id=business.id,
        audit_run_id=audit.id if audit else None,
        version=result.version,
        score=result.score,
        band=result.band.value,
        recommended_next_action=result.recommended_next_action.value,
        created_at=result.created_at,
    )
    session.add(row)
    session.flush()
    for component in result.components:
        session.add(
            OpportunityComponent(
                opportunity_score_id=row.id,
                code=component.code,
                category=component.category,
                points=component.points,
                max_points=component.max_points,
                evidence=component.evidence,
                source_type=component.source_type,
                confidence=component.confidence,
            )
        )
    for hold in result.holds:
        session.add(
            OpportunityHold(
                opportunity_score_id=row.id,
                code=hold.code,
                reason=hold.reason,
                severity=hold.severity,
                evidence=hold.evidence,
            )
        )
    current = LeadState(business.state)
    if current == LeadState.AUDITED:
        validate_transition(current, LeadState.SCORED)
        business.state = LeadState.SCORED.value
        session.add(
            PipelineEvent(
                business_id=business.id,
                from_state=current.value,
                to_state=LeadState.SCORED.value,
                actor="score",
                reason="opportunity_score_v1",
            )
        )
    return row


async def execute_score(
    session: Session, request: OpportunityScoreRequest, business: Business
) -> tuple[OpportunityScore, OpportunityScoreResult]:
    context, audit = _latest_context(session, business)
    result = score_opportunity(context)
    row = persist_score(session, business, result, audit)
    session.commit()
    session.refresh(row)
    return row, result
