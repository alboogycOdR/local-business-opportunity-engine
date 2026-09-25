"""Deterministic, evidence-backed Opportunity Score v1 rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from lboe_domain import (
    AuditFinding,
    OpportunityScoreComponent,
    OpportunityScoreHold,
    OpportunityScoreResult,
    RecommendedNextAction,
    ScoreBand,
)


@dataclass(frozen=True)
class ScoreContext:
    business_id: UUID
    display_name: str
    category: str | None
    address_text: str | None
    website_url: str | None
    phone: str | None
    state: str
    audit_findings: list[AuditFinding] = field(default_factory=list)
    suppressed: bool = False
    ambiguous: bool = False
    source_count: int = 0


def _finding(context: ScoreContext, code: str) -> AuditFinding | None:
    return next((item for item in context.audit_findings if item.code == code), None)


def _component(
    code: str,
    points: int,
    category: str,
    max_points: int,
    evidence: dict[str, Any],
    source_type: str = "derived",
    confidence: float = 1.0,
) -> OpportunityScoreComponent:
    return OpportunityScoreComponent(
        code=code,
        points=points,
        category=category,
        max_points=max_points,
        evidence=evidence,
        source_type=source_type,
        confidence=confidence,
    )


def score_opportunity(context: ScoreContext) -> OpportunityScoreResult:
    components: list[OpportunityScoreComponent] = []
    holds: list[OpportunityScoreHold] = []

    def add(
        code: str, points: int, category: str, maximum: int, evidence: dict[str, Any], source: str = "derived"
    ) -> None:
        components.append(_component(code, points, category, maximum, evidence, source))

    findings = {item.code: item for item in context.audit_findings}
    availability = next((item for item in context.audit_findings if item.category == "availability"), None)

    # A: addressable gap, capped at 55.
    gap = 0
    if not context.website_url:
        add("NO_WEBSITE", 20, "addressable_gap", 55, {"website": None}, "business")
        gap += 20
    elif availability and availability.code in {
        "WEBSITE_UNREACHABLE",
        "DNS_FAILURE",
        "TLS_FAILURE",
        "HTTP_ERROR",
        "WEBSITE_INVALID_URL",
        "REDIRECT_LOOP",
    }:
        code = availability.code
        add(
            code, 20, "addressable_gap", 55, {"status": availability.status, "evidence": availability.evidence}, "audit"
        )
        gap += 20
    elif availability and availability.code == "WEBSITE_HEALTHY":
        add("WEBSITE_HEALTHY_REDUCES_GAP", -8, "addressable_gap", 55, {"status": "healthy"}, "audit")
        gap -= 8

    gap_rules = {
        "BOOKING_PATH": ("NO_BOOKING_PATH", 8),
        "WHATSAPP_CTA": ("NO_WHATSAPP_CTA", 5),
        "CLICK_TO_CALL": ("NO_CLICK_TO_CALL", 3),
        "CONTACT_FORM": ("NO_CONTACT_FORM", 3),
        "SERVICE_CATALOGUE": ("NO_SERVICE_CATALOGUE", 3),
        "HORIZONTAL_OVERFLOW": ("MOBILE_OVERFLOW", 5),
        "VIEWPORT_META_PRESENT": ("MISSING_VIEWPORT_META", 3),
        "TITLE_PRESENT": ("MISSING_TITLE", 2),
        "META_DESCRIPTION_PRESENT": ("MISSING_META_DESCRIPTION", 2),
        "H1_PRESENT": ("MISSING_H1", 2),
    }
    for detected_code, (missing_code, points) in gap_rules.items():
        item = findings.get(detected_code)
        missing = item is None or item.status in {"missing", "not_detected"}
        if detected_code == "HORIZONTAL_OVERFLOW":
            missing = item is not None and item.status == "detected"
        if missing:
            add(
                missing_code,
                points,
                "addressable_gap",
                55,
                {"finding": item.model_dump(mode="json") if item else "not_observed"},
                "audit",
            )
            gap += points
    alt = findings.get("IMAGE_ALT_COVERAGE")
    if alt and isinstance(alt.observed_value, dict) and alt.observed_value.get("missing", 0) > 0:
        add("LOW_IMAGE_ALT_COVERAGE", 2, "addressable_gap", 55, {"finding": alt.model_dump(mode="json")}, "audit")
        gap += 2
    for code, points in (("BROWSER_CONSOLE_ERRORS", 2), ("FAILED_FIRST_PARTY_REQUESTS", 2)):
        item = findings.get(code)
        if item and item.status == "detected":
            add(code, points, "addressable_gap", 55, {"finding": item.model_dump(mode="json")}, "audit")
            gap += points

    gap = max(0, min(55, gap))

    # B: commercial readiness, capped at 20.
    readiness = 0
    if context.state not in {"REJECTED", "SUPPRESSED"}:
        add("ACTIVE_DISCOVERY", 4, "commercial_readiness", 20, {"state": context.state}, "pipeline")
        readiness += 4
    if context.category:
        add("CATEGORY_VERIFIED", 4, "commercial_readiness", 20, {"category": context.category}, "business")
        readiness += 4
    if findings.get("SERVICE_CATALOGUE") and findings["SERVICE_CATALOGUE"].status == "detected":
        add(
            "SERVICE_EVIDENCE",
            4,
            "commercial_readiness",
            20,
            {"finding": findings["SERVICE_CATALOGUE"].model_dump(mode="json")},
            "audit",
        )
        readiness += 4
    if context.display_name and (context.address_text or context.website_url):
        add("FACTS_FOR_DEMO", 4, "commercial_readiness", 20, {"name": True, "location_or_site": True}, "business")
        readiness += 4
    if context.website_url or context.source_count > 0:
        add(
            "DIGITAL_ACTIVITY",
            4,
            "commercial_readiness",
            20,
            {"website": bool(context.website_url), "source_count": context.source_count},
            "derived",
        )
        readiness += 4

    # C: safe reachability only; never consent.
    reachability = 0
    if context.website_url:
        add("VERIFIED_WEBSITE", 4, "reachability", 10, {"website": context.website_url}, "business")
        reachability += 4
    if context.phone:
        add("VERIFIED_PHONE", 3, "reachability", 10, {"phone_present": True}, "contact")
        reachability += 3
    if availability and availability.code == "WEBSITE_HEALTHY":
        add("REACHABLE_PUBLIC_WEBSITE", 3, "reachability", 10, {"status": availability.status}, "audit")
        reachability += 3

    # D: truthful demo confidence, capped at 15.
    confidence = 0
    for code, points, evidence in (
        ("VERIFIED_BUSINESS_NAME", 3, {"display_name": context.display_name}),
        ("VERIFIED_CATEGORY", 3, {"category": context.category}),
        ("VERIFIED_LOCALITY", 3, {"address_text": context.address_text}),
        ("AUDIT_EVIDENCE_AVAILABLE", 3, {"finding_count": len(context.audit_findings)}),
    ):
        if (
            (code == "VERIFIED_LOCALITY" and not context.address_text)
            or (code == "VERIFIED_CATEGORY" and not context.category)
            or (code == "AUDIT_EVIDENCE_AVAILABLE" and not context.audit_findings)
        ):
            continue
        add(code, points, "demo_confidence", 15, evidence, "derived")
        confidence += points
    if not context.ambiguous:
        add("IDENTITY_UNAMBIGUOUS", 3, "demo_confidence", 15, {"ambiguous": False}, "identity")
        confidence += 3

    if context.suppressed:
        holds.append(
            OpportunityScoreHold(
                code="SUPPRESSED",
                reason="Operator suppression is active",
                severity="high",
                evidence={"suppressed": True},
            )
        )
    if context.ambiguous:
        holds.append(
            OpportunityScoreHold(
                code="AMBIGUOUS_IDENTITY",
                reason="Identity resolution remains unresolved",
                severity="high",
                evidence={"ambiguous": True},
            )
        )
    if not context.website_url and not context.phone:
        holds.append(
            OpportunityScoreHold(
                code="NO_VERIFIABLE_CONTACT",
                reason="No website or phone is available",
                severity="high",
                evidence={"website": False, "phone": False},
            )
        )
    if context.website_url and not context.audit_findings:
        holds.append(
            OpportunityScoreHold(
                code="INSUFFICIENT_FACTS_FOR_DEMO",
                reason="Website exists but has not been audited",
                severity="medium",
                evidence={"audit": False},
            )
        )

    total = max(0, min(100, gap + readiness + reachability + confidence))
    band = ScoreBand.HIGH if total >= 70 else ScoreBand.MEDIUM if total >= 50 else ScoreBand.LOW
    if any(item.code == "SUPPRESSED" for item in holds):
        action = RecommendedNextAction.DO_NOT_CONTACT
    elif any(item.code == "AMBIGUOUS_IDENTITY" for item in holds):
        action = RecommendedNextAction.MANUAL_REVIEW
    elif any(item.code == "NO_VERIFIABLE_CONTACT" for item in holds):
        action = RecommendedNextAction.ARCHIVE
    elif context.website_url and not context.audit_findings:
        action = RecommendedNextAction.AUDIT_REQUIRED
    elif not context.website_url and not any(item.code == "NO_VERIFIABLE_CONTACT" for item in holds):
        action = RecommendedNextAction.GENERATE_DEMO
    elif any(
        item.code in {"NO_BOOKING_PATH", "NO_WHATSAPP_CTA", "NO_CONTACT_FORM", "NO_CLICK_TO_CALL"}
        for item in components
    ):
        action = RecommendedNextAction.CONVERSION_UPGRADE_OFFER
    elif gap >= 12 and confidence >= 9:
        action = RecommendedNextAction.GENERATE_DEMO
    elif gap > 0:
        action = RecommendedNextAction.TECHNICAL_CLEANUP_OFFER
    else:
        action = RecommendedNextAction.SCORE_ONLY
    return OpportunityScoreResult(
        business_id=context.business_id,
        score=total,
        band=band,
        components=components,
        holds=holds,
        recommended_next_action=action,
    )
