from __future__ import annotations

from lboe_api.brief_service import build_brief, execute_brief
from lboe_api.db import (
    AuditFinding,
    AuditRun,
    Base,
    Business,
    Campaign,
    Contact,
    OpportunityComponent,
    OpportunityScore,
    SuppressionEntry,
    make_engine,
)
from lboe_domain import BusinessBriefRequest
from sqlalchemy.orm import Session


def seeded_business(session: Session, state: str = "SCORED") -> Business:
    campaign = Campaign(name="brief-test", vertical="hair_salon")
    session.add(campaign)
    session.flush()
    business = Business(
        campaign_id=campaign.id,
        display_name="Excentric-style Salon",
        category="Hairdresser",
        address_text="Cape Town",
        identity_key="excentric style salon|cape town",
        state=state,
    )
    session.add(business)
    session.flush()
    session.add(Contact(business_id=business.id, channel="website", value="https://example.test"))
    return business


def test_healthy_brief_is_neutral_and_source_backed() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = seeded_business(session)
        audit = AuditRun(business_id=business.id, auditor_version="test", status="succeeded")
        session.add(audit)
        session.flush()
        session.add_all(
            [
                AuditFinding(
                    audit_run_id=audit.id,
                    code="WEBSITE_HEALTHY",
                    category="availability",
                    severity="info",
                    status="detected",
                    deterministic=True,
                    evidence={"items": []},
                    source_url="https://example.test",
                    confidence=1.0,
                    auditor_version="test",
                ),
                AuditFinding(
                    audit_run_id=audit.id,
                    code="BOOKING_PATH",
                    category="conversion",
                    severity="info",
                    status="detected",
                    deterministic=True,
                    evidence={"items": []},
                    source_url="https://example.test",
                    confidence=1.0,
                    auditor_version="test",
                ),
                AuditFinding(
                    audit_run_id=audit.id,
                    code="WHATSAPP_CTA",
                    category="conversion",
                    severity="info",
                    status="detected",
                    deterministic=True,
                    evidence={"items": []},
                    source_url="https://example.test",
                    confidence=1.0,
                    auditor_version="test",
                ),
                AuditFinding(
                    audit_run_id=audit.id,
                    code="SERVICE_CATALOGUE",
                    category="conversion",
                    severity="info",
                    status="detected",
                    deterministic=True,
                    evidence={"items": []},
                    source_url="https://example.test",
                    confidence=1.0,
                    auditor_version="test",
                ),
            ]
        )
        score = OpportunityScore(
            business_id=business.id,
            audit_run_id=audit.id,
            version="opportunity-v1",
            score=45,
            band="low",
            recommended_next_action="score_only",
        )
        session.add(score)
        session.flush()
        session.add(
            OpportunityComponent(
                opportunity_score_id=score.id,
                code="WEBSITE_HEALTHY_REDUCES_GAP",
                category="addressable_gap",
                points=-8,
                max_points=55,
                evidence={"status": "healthy"},
                source_type="audit",
                confidence=1.0,
            )
        )
        session.commit()
        brief = build_brief(session, business)
        assert brief.recommended_action.code == "score_only"
        assert any(item.code == "LOW_REBUILD_PRIORITY" for item in brief.opportunities)
        assert not any(word in brief.summary.lower() for word in ("ugly", "bad business", "unprofessional"))
        assert all(item.evidence for item in brief.verified_facts)


def test_no_website_brief_surfaces_starter_opportunity() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = seeded_business(session, state="DISCOVERED")
        session.query(Contact).delete()
        session.commit()
        brief = build_brief(session, business)
        assert "Website" in brief.unknowns
        assert brief.recommended_action.code == "manual_review"


def test_suppressed_brief_is_do_not_contact() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = seeded_business(session)
        session.add(SuppressionEntry(business_id=business.id, reason="operator hold"))
        session.commit()
        brief = build_brief(session, business)
        assert brief.recommended_action.code == "do_not_contact"


def test_brief_history_is_append_only() -> None:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = seeded_business(session)
        first, _ = __import__("asyncio").run(
            execute_brief(session, BusinessBriefRequest(business_id=business.id, idempotency_key="one"), business)
        )
        second, _ = __import__("asyncio").run(
            execute_brief(session, BusinessBriefRequest(business_id=business.id, idempotency_key="two"), business)
        )
        assert first.id != second.id
