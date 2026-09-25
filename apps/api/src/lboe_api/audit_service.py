"""Audit orchestration and persistence; provider details stay behind adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from lboe_domain import AuditAdapter, AuditRequest, AuditResult, LeadState, validate_transition
from sqlalchemy.orm import Session

from .db import AuditArtifact, AuditFinding, AuditRun, Business, PipelineEvent, Website


def audit_idempotency_key(request: AuditRequest) -> str:
    material = {
        "business_id": str(request.business_id),
        "website_url": request.website_url,
        "caller_key": request.idempotency_key,
        "max_pages": request.max_pages,
    }
    return "audit:" + hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def persist_audit(session: Session, business: Business, request: AuditRequest, result: AuditResult) -> AuditRun:
    started_at = datetime.now(UTC)
    run = AuditRun(
        business_id=business.id,
        auditor_version=result.auditor_version,
        status="succeeded",
        started_at=started_at,
        completed_at=datetime.now(UTC),
        technical_metadata=result.technical_metadata,
    )
    session.add(run)
    session.flush()
    website = Website(
        business_id=business.id,
        discovered_url=result.website.requested_url or request.website_url or "",
        normalized_url=result.website.normalized_url,
        final_url=result.website.final_url,
        http_status=result.website.http_status,
        resolution_status=result.website.status,
        checked_at=result.website.checked_at,
    )
    session.add(website)
    session.flush()
    run.website_id = website.id
    for finding in result.findings:
        value = (
            finding.observed_value
            if isinstance(finding.observed_value, dict)
            else ({"value": finding.observed_value} if finding.observed_value is not None else None)
        )
        session.add(
            AuditFinding(
                audit_run_id=run.id,
                code=finding.code,
                category=finding.category,
                severity=finding.severity,
                deterministic=finding.deterministic,
                status=finding.status,
                observed_value=value,
                evidence={"items": [item.model_dump(mode="json") for item in finding.evidence]},
                source_url=finding.source_url,
                confidence=finding.confidence,
                observed_at=finding.observed_at,
                auditor_version=finding.auditor_version,
            )
        )
    for artifact in result.artifacts:
        session.add(
            AuditArtifact(
                audit_run_id=run.id,
                kind=artifact.kind,
                path=artifact.path,
                mime_type=artifact.mime_type,
                byte_size=artifact.byte_size,
            )
        )
    current = LeadState(business.state)
    if current != LeadState.AUDITED:
        validate_transition(current, LeadState.AUDITING)
        business.state = LeadState.AUDITING.value
        session.add(
            PipelineEvent(
                business_id=business.id,
                from_state=current.value,
                to_state=LeadState.AUDITING.value,
                actor="audit",
                reason="website_audit_started",
            )
        )
        session.flush()
        business.state = LeadState.AUDITED.value
        session.add(
            PipelineEvent(
                business_id=business.id,
                from_state=LeadState.AUDITING.value,
                to_state=LeadState.AUDITED.value,
                actor="audit",
                reason="website_audit_completed",
            )
        )
    return run


async def execute_audit(
    session: Session, adapter: AuditAdapter, business: Business, request: AuditRequest
) -> tuple[AuditRun, AuditResult]:
    result = await adapter.audit(request)
    run = persist_audit(session, business, request, result)
    session.commit()
    session.refresh(run)
    return run, result
