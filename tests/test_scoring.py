from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from lboe_api.db import Base, Business, Campaign, make_engine
from lboe_api.scoring_service import execute_score
from lboe_domain import AuditEvidence, AuditFinding, OpportunityScoreRequest, RecommendedNextAction
from lboe_scoring import ScoreContext, score_opportunity
from sqlalchemy.orm import Session


def finding(code: str, status: str = "detected", value: object = True) -> AuditFinding:
    return AuditFinding(
        code=code,
        category="conversion" if code not in {"WEBSITE_HEALTHY", "IMAGE_ALT_COVERAGE"} else "availability",
        status=status,
        observed_value=value,
        evidence=[AuditEvidence(kind="test", value=value)],
    )


def context(**kwargs: object) -> ScoreContext:
    values: dict[str, object] = {
        "business_id": uuid.uuid4(),
        "display_name": "Test Salon",
        "category": "hair_salon",
        "address_text": "Cape Town",
        "website_url": None,
        "phone": "+27123456789",
        "state": "DISCOVERED",
        "audit_findings": [],
        "source_count": 2,
    }
    values.update(kwargs)
    return ScoreContext(**cast(Any, values))


def test_no_website_is_high_gap_and_demo_candidate() -> None:
    result = score_opportunity(context())
    assert any(item.code == "NO_WEBSITE" for item in result.components)
    assert result.recommended_next_action == RecommendedNextAction.GENERATE_DEMO
    assert result.score >= 40


def test_healthy_complete_site_is_lower_gap_and_score_only() -> None:
    codes = [
        finding("WEBSITE_HEALTHY"),
        finding("BOOKING_PATH"),
        finding("WHATSAPP_CTA"),
        finding("CLICK_TO_CALL"),
        finding("CONTACT_FORM"),
        finding("SERVICE_CATALOGUE"),
        finding("VIEWPORT_META_PRESENT"),
        finding("TITLE_PRESENT"),
        finding("META_DESCRIPTION_PRESENT"),
        finding("H1_PRESENT"),
    ]
    result = score_opportunity(context(website_url="https://example.test", audit_findings=codes))
    assert result.score < 70
    assert result.recommended_next_action in {
        RecommendedNextAction.SCORE_ONLY,
        RecommendedNextAction.TECHNICAL_CLEANUP_OFFER,
    }


def test_healthy_site_missing_conversion_paths_gets_upgrade_action() -> None:
    result = score_opportunity(
        context(
            website_url="https://example.test",
            audit_findings=[finding("WEBSITE_HEALTHY"), finding("BOOKING_PATH", "not_detected", False)],
        )
    )
    assert any(item.code == "NO_BOOKING_PATH" for item in result.components)
    assert result.recommended_next_action == RecommendedNextAction.CONVERSION_UPGRADE_OFFER


def test_suppressed_and_ambiguous_holds_override_action() -> None:
    suppressed = score_opportunity(context(suppressed=True))
    assert any(item.code == "SUPPRESSED" for item in suppressed.holds)
    assert suppressed.recommended_next_action == RecommendedNextAction.DO_NOT_CONTACT
    ambiguous = score_opportunity(context(ambiguous=True, website_url="https://example.test"))
    assert any(item.code == "AMBIGUOUS_IDENTITY" for item in ambiguous.holds)
    assert ambiguous.recommended_next_action == RecommendedNextAction.MANUAL_REVIEW


def test_website_without_audit_requires_audit() -> None:
    result = score_opportunity(context(website_url="https://example.test"))
    assert result.recommended_next_action == RecommendedNextAction.AUDIT_REQUIRED


def test_score_history_is_append_only_and_audited_lead_transitions() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        campaign = Campaign(name="test", vertical="hair_salon")
        session.add(campaign)
        session.flush()
        business = Business(
            campaign_id=campaign.id,
            display_name="Test Salon",
            category="Hair salon",
            address_text="Cape Town",
            identity_key="test salon|cape town",
            state="AUDITED",
        )
        session.add(business)
        session.commit()
        first, _ = asyncio.run(
            execute_score(session, OpportunityScoreRequest(business_id=business.id, idempotency_key="a"), business)
        )
        business.state = "AUDITED"
        second, _ = asyncio.run(
            execute_score(session, OpportunityScoreRequest(business_id=business.id, idempotency_key="b"), business)
        )
        assert first.id != second.id
        assert session.query(type(first)).filter_by(business_id=business.id).count() == 2
