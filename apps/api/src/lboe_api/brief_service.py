"""Deterministic Business Brief generation and persistence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from lboe_domain import (
    BusinessBriefFact as BriefFact,
)
from lboe_domain import (
    BusinessBriefOpportunity as BriefOpportunity,
)
from lboe_domain import (
    BusinessBriefRecommendedAction,
    BusinessBriefRequest,
    BusinessBriefResult,
    BusinessBriefSection,
)
from lboe_domain import (
    BusinessBriefRisk as BriefRisk,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import (
    AuditFinding,
    AuditRun,
    Business,
    BusinessBrief,
    BusinessBriefFact,
    BusinessBriefOpportunity,
    BusinessBriefRisk,
    BusinessExternalIdentity,
    Contact,
    OpportunityComponent,
    OpportunityHold,
    OpportunityScore,
    SuppressionEntry,
    Website,
)

ACTION_TEXT: dict[str, tuple[str, str]] = {
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


def brief_idempotency_key(request: BusinessBriefRequest) -> str:
    material = {
        "business_id": str(request.business_id),
        "caller_key": request.idempotency_key,
        "version": "business-brief-v1",
    }
    return "brief:" + hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _fact(
    fact_type: str,
    label: str,
    value: Any,
    source_type: str,
    evidence: dict[str, Any],
    confidence: float = 1.0,
    status: str = "verified",
) -> BriefFact:
    return BriefFact(
        fact_type=fact_type,
        label=label,
        value=value,
        source_type=source_type,
        evidence=evidence,
        confidence=confidence,
        status=status,
    )


def build_brief(session: Session, business: Business) -> BusinessBriefResult:
    contacts = session.scalars(select(Contact).where(Contact.business_id == business.id)).all()
    identities = session.scalars(
        select(BusinessExternalIdentity).where(BusinessExternalIdentity.business_id == business.id)
    ).all()
    audit = session.scalar(
        select(AuditRun).where(AuditRun.business_id == business.id).order_by(AuditRun.completed_at.desc())
    )
    findings = session.scalars(select(AuditFinding).where(AuditFinding.audit_run_id == audit.id)).all() if audit else []
    score = session.scalar(
        select(OpportunityScore)
        .where(OpportunityScore.business_id == business.id)
        .order_by(OpportunityScore.created_at.desc())
    )
    score_components = (
        session.scalars(select(OpportunityComponent).where(OpportunityComponent.opportunity_score_id == score.id)).all()
        if score
        else []
    )
    holds = (
        session.scalars(select(OpportunityHold).where(OpportunityHold.opportunity_score_id == score.id)).all()
        if score
        else []
    )
    suppressed = (
        session.scalar(select(SuppressionEntry.id).where(SuppressionEntry.business_id == business.id)) is not None
    )
    facts: list[BriefFact] = [
        _fact(
            "identity", "Business name", business.display_name, "canonical_business", {"business_id": str(business.id)}
        ),
    ]
    if business.category:
        facts.append(
            _fact("identity", "Category", business.category, "canonical_business", {"business_id": str(business.id)})
        )
    else:
        facts.append(_fact("identity", "Category", None, "unknown", {"reason": "not recorded"}, status="unknown"))
    if business.address_text:
        facts.append(
            _fact(
                "identity",
                "Address/locality",
                business.address_text,
                "canonical_business",
                {"business_id": str(business.id)},
            )
        )
    else:
        facts.append(
            _fact("identity", "Address/locality", None, "unknown", {"reason": "not recorded"}, status="unknown")
        )
    for identity in identities:
        facts.append(
            _fact(
                "identity",
                f"External identity ({identity.source})",
                identity.source_id,
                "external_identity",
                {"identity_id": str(identity.id), "source": identity.source},
                identity.confidence,
            )
        )
    for contact in contacts:
        facts.append(_fact("contact", contact.channel, contact.value, "contact", {"contact_id": str(contact.id)}))
    website = next((contact.value for contact in contacts if contact.channel == "website"), None)
    website_row = session.scalar(
        select(Website).where(Website.business_id == business.id).order_by(Website.checked_at.desc())
    )
    if website_row:
        facts.extend(
            [
                _fact(
                    "website",
                    "Website status",
                    website_row.resolution_status,
                    "website_resolver",
                    {"website_id": str(website_row.id), "checked_at": website_row.checked_at.isoformat()},
                ),
                _fact(
                    "website",
                    "Final URL",
                    website_row.final_url,
                    "website_resolver",
                    {"website_id": str(website_row.id)},
                ),
                _fact(
                    "website",
                    "HTTP status",
                    website_row.http_status,
                    "website_resolver",
                    {"website_id": str(website_row.id)},
                ),
            ]
        )
    elif not website:
        facts.append(
            _fact("website", "Website", None, "unknown", {"reason": "no discovered website"}, status="unknown")
        )
    audit_id = str(audit.id) if audit else None
    for finding in findings:
        facts.append(
            _fact(
                "audit_quality"
                if finding.category in {"seo", "technical", "mobile", "accessibility"}
                else "conversion",
                finding.code,
                finding.observed_value,
                "audit",
                {"audit_run_id": audit_id, "source_url": finding.source_url, "finding_id": str(finding.id)},
                finding.confidence,
            )
        )
    if score:
        facts.extend(
            [
                _fact("score", "Opportunity score", score.score, "opportunity_score", {"score_id": str(score.id)}),
                _fact("score", "Score band", score.band, "opportunity_score", {"score_id": str(score.id)}),
                _fact(
                    "score",
                    "Recommended action",
                    score.recommended_next_action,
                    "opportunity_score",
                    {"score_id": str(score.id)},
                ),
            ]
        )
    else:
        facts.append(
            _fact("score", "Opportunity score", None, "unknown", {"reason": "no score exists"}, status="unknown")
        )

    opportunities: list[BriefOpportunity] = []
    by_code = {item.code: item for item in score_components}
    if "NO_WEBSITE" in by_code:
        opportunities.append(
            BriefOpportunity(
                code="NO_WEBSITE",
                title="Starter website opportunity",
                description="No website was verified from available sources.",
                priority="high",
                evidence=by_code["NO_WEBSITE"].evidence,
            )
        )
    for code, title, description in (
        (
            "WEBSITE_UNREACHABLE",
            "Website availability issue",
            "The discovered website was not reachable during the audit.",
        ),
        ("NO_BOOKING_PATH", "Booking flow opportunity", "No booking path was detected in the audited homepage."),
        (
            "NO_WHATSAPP_CTA",
            "WhatsApp conversion opportunity",
            "No WhatsApp action was detected in the audited homepage.",
        ),
        (
            "NO_CLICK_TO_CALL",
            "Click-to-call opportunity",
            "No click-to-call action was detected in the audited homepage.",
        ),
        ("NO_CONTACT_FORM", "Contact form opportunity", "No contact form was detected in the audited homepage."),
        (
            "NO_SERVICE_CATALOGUE",
            "Service catalogue opportunity",
            "No service or catalogue path was detected in the audited homepage.",
        ),
    ):
        if code in by_code:
            opportunities.append(
                BriefOpportunity(
                    code=code, title=title, description=description, priority="medium", evidence=by_code[code].evidence
                )
            )
    technical_codes = {
        "MISSING_H1",
        "LOW_IMAGE_ALT_COVERAGE",
        "BROWSER_CONSOLE_ERRORS",
        "FAILED_FIRST_PARTY_REQUESTS",
        "MISSING_META_DESCRIPTION",
        "MISSING_TITLE",
        "MISSING_VIEWPORT_META",
        "MOBILE_OVERFLOW",
    }
    technical = [item for item in score_components if item.code in technical_codes]
    if technical:
        opportunities.append(
            BriefOpportunity(
                code="TECHNICAL_CLEANUP",
                title="Technical cleanup opportunity",
                description=(
                    "Objective audit evidence identifies technical, accessibility, or SEO hygiene items for review."
                ),
                priority="low",
                evidence={"components": [item.code for item in technical]},
            )
        )
    if score and score.recommended_next_action == "score_only" and not opportunities:
        opportunities.append(
            BriefOpportunity(
                code="LOW_REBUILD_PRIORITY",
                title="Low rebuild priority",
                description="Current evidence shows an active website with multiple conversion paths.",
                priority="low",
                evidence={"score_id": str(score.id)},
            )
        )

    risks: list[BriefRisk] = []
    for hold in holds:
        title = {
            "SUPPRESSED": "Suppression hold",
            "AMBIGUOUS_IDENTITY": "Identity ambiguity",
            "NO_VERIFIABLE_CONTACT": "No verifiable contact",
            "INSUFFICIENT_FACTS_FOR_DEMO": "Insufficient facts",
        }.get(hold.code, hold.code.replace("_", " ").title())
        risks.append(
            BriefRisk(
                code=hold.code, title=title, description=hold.reason, severity=hold.severity, evidence=hold.evidence
            )
        )
    if website and not audit:
        risks.append(
            BriefRisk(
                code="NO_AUDIT_YET",
                title="Audit not available",
                description="A website is recorded but no audit run is available yet.",
                severity="medium",
                evidence={"website": website},
            )
        )
    if audit and any(
        item.code in {"WEBSITE_UNREACHABLE", "DNS_FAILURE", "TLS_FAILURE", "HTTP_ERROR"} for item in findings
    ):
        risks.append(
            BriefRisk(
                code="UNREACHABLE_WEBSITE",
                title="Website availability risk",
                description="The audited website had an availability issue at observation time.",
                severity="high",
                evidence={"audit_run_id": str(audit.id)},
            )
        )
    action_code = score.recommended_next_action if score else ("audit_required" if website else "manual_review")
    if suppressed:
        action_code = "do_not_contact"
    label, rationale = ACTION_TEXT[action_code]
    action = BusinessBriefRecommendedAction(code=action_code, label=label, rationale=rationale)
    category_label = business.category or "an unclassified business"
    summary = f"{business.display_name} is recorded as {category_label} with {len(facts)} source-backed facts."
    if score:
        summary += (
            f" The current Opportunity Score is {score.score} ({score.band}); the evidence supports "
            f"{action_code.replace('_', ' ')}."
        )
    else:
        summary += " No Opportunity Score is available yet."
    confidence = min(
        1.0,
        sum(item.confidence for item in facts if item.status == "verified")
        / max(1, len([item for item in facts if item.status == "verified"])),
    )
    sections = [
        BusinessBriefSection(
            name="identity",
            summary="Verified identity and location facts.",
            facts=[item for item in facts if item.fact_type == "identity"],
        ),
        BusinessBriefSection(
            name="contact",
            summary="Recorded contact channels; presence is not consent.",
            facts=[item for item in facts if item.fact_type == "contact"],
        ),
        BusinessBriefSection(
            name="website",
            summary="Website resolution and audit facts.",
            facts=[item for item in facts if item.fact_type in {"website", "conversion", "audit_quality"}],
        ),
        BusinessBriefSection(
            name="score",
            summary="Deterministic score evidence.",
            facts=[item for item in facts if item.fact_type == "score"],
        ),
    ]
    unknowns = [item.label for item in facts if item.status == "unknown"]
    evidence_references = [item.evidence for item in facts if item.evidence]
    return BusinessBriefResult(
        business_id=business.id,
        score_id=score.id if score else None,
        audit_run_id=audit.id if audit else None,
        summary=summary,
        sections=sections,
        verified_facts=[item for item in facts if item.status == "verified"],
        unknowns=unknowns,
        opportunities=opportunities,
        risks=risks,
        recommended_action=action,
        evidence_references=evidence_references,
        confidence=confidence,
    )


def persist_brief(session: Session, result: BusinessBriefResult) -> BusinessBrief:
    row = BusinessBrief(
        business_id=result.business_id,
        score_id=result.score_id,
        audit_run_id=result.audit_run_id,
        version=result.version,
        summary=result.summary,
        recommended_next_action=result.recommended_action.code,
        confidence=result.confidence,
        created_at=result.created_at,
    )
    session.add(row)
    session.flush()
    for fact in [
        *result.verified_facts,
        *[item for section in result.sections for item in section.facts if item.status == "unknown"],
    ]:
        session.add(
            BusinessBriefFact(
                business_brief_id=row.id,
                fact_type=fact.fact_type,
                label=fact.label,
                value=fact.value,
                source_type=fact.source_type,
                evidence=fact.evidence,
                confidence=fact.confidence,
            )
        )
    for opportunity in result.opportunities:
        session.add(
            BusinessBriefOpportunity(
                business_brief_id=row.id,
                code=opportunity.code,
                title=opportunity.title,
                description=opportunity.description,
                priority=opportunity.priority,
                evidence=opportunity.evidence,
            )
        )
    for risk in result.risks:
        session.add(
            BusinessBriefRisk(
                business_brief_id=row.id,
                code=risk.code,
                title=risk.title,
                description=risk.description,
                severity=risk.severity,
                evidence=risk.evidence,
            )
        )
    return row


async def execute_brief(
    session: Session, request: BusinessBriefRequest, business: Business
) -> tuple[BusinessBrief, BusinessBriefResult]:
    result = build_brief(session, business)
    row = persist_brief(session, result)
    session.commit()
    session.refresh(row)
    return row, result
