import uuid
from datetime import UTC, datetime, timedelta

from lboe_api.db import (
    Base,
    Business,
    Campaign,
    Job,
    LeadCrmEvent,
    OpportunityScore,
    OutreachExecutionRecord,
    PipelineEvent,
    SuppressionEntry,
    make_engine,
)
from lboe_api.reporting_service import build_pilot_report
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_empty_report_is_zero_filled() -> None:
    session = _session()
    report = build_pilot_report(session)
    assert all(item["count"] == 0 for item in report["funnel_metrics"])
    assert report["warnings"]


def test_campaign_and_date_filters() -> None:
    session = _session()
    now = datetime.now(UTC)
    campaign_a = Campaign(name="A", vertical="salon", geography="Cape Town")
    campaign_b = Campaign(name="B", vertical="restaurant", geography="Cape Town")
    session.add_all([campaign_a, campaign_b])
    session.flush()
    business_a = Business(campaign_id=campaign_a.id, display_name="A Salon", category="salon", identity_key="a")
    business_b = Business(campaign_id=campaign_b.id, display_name="B Cafe", category="cafe", identity_key="b")
    session.add_all([business_a, business_b])
    session.flush()
    session.add_all(
        [
            PipelineEvent(business_id=business_a.id, from_state=None, to_state="DISCOVERED", created_at=now),
            PipelineEvent(business_id=business_a.id, from_state="DISCOVERED", to_state="DEDUPED", created_at=now),
            PipelineEvent(
                business_id=business_b.id, from_state=None, to_state="DISCOVERED", created_at=now - timedelta(days=30)
            ),
            Job(
                job_type="X",
                idempotency_key="job-a",
                status="failed",
                payload={"business_id": str(business_a.id)},
                created_at=now,
            ),
        ]
    )
    session.commit()
    report = build_pilot_report(session, campaign_id=campaign_a.id, start_date=now.date(), end_date=now.date())
    counts = {item["stage"]: item["count"] for item in report["funnel_metrics"]}
    assert report["vertical"] == "salon"
    assert counts["DISCOVERED"] == 1
    assert report["details"] == {}
    detailed = build_pilot_report(session, campaign_id=campaign_a.id, include_details=True)
    assert detailed["details"]["transitions"]["NONE->DISCOVERED"] == 1


def test_funnel_quality_workload_and_safety_metrics() -> None:
    session = _session()
    now = datetime.now(UTC)
    campaign = Campaign(name="Pilot", vertical="salon", geography="Cape Town")
    session.add(campaign)
    session.flush()
    active = Business(
        campaign_id=campaign.id,
        display_name="Active Salon",
        category="salon",
        identity_key="active",
        state="MEETING",
    )
    suppressed = Business(
        campaign_id=campaign.id,
        display_name="Suppressed Salon",
        category="salon",
        identity_key="suppressed",
        state="SUPPRESSED",
    )
    session.add_all([active, suppressed])
    session.flush()
    session.add_all(
        [
            PipelineEvent(business_id=active.id, from_state=None, to_state="DISCOVERED", created_at=now),
            PipelineEvent(business_id=active.id, from_state="DISCOVERED", to_state="DEDUPED", created_at=now),
            PipelineEvent(business_id=active.id, from_state="CONTACTED", to_state="REPLIED", created_at=now),
            PipelineEvent(business_id=active.id, from_state="REPLIED", to_state="MEETING", created_at=now),
            OpportunityScore(
                business_id=active.id,
                version="opportunity-v1",
                score=48,
                band="medium",
                recommended_next_action="score_only",
                created_at=now,
            ),
            OutreachExecutionRecord(
                business_id=active.id,
                outreach_draft_package_id=uuid.uuid4(),
                outreach_draft_message_id=uuid.uuid4(),
                channel="email",
                operator="operator",
                sent_at=now,
                resulting_business_state="CONTACTED",
            ),
            LeadCrmEvent(
                business_id=active.id,
                event_type="reply_received",
                channel="email",
                operator="operator",
                occurred_at=now,
                summary="Reply recorded",
                resulting_business_state="REPLIED",
            ),
            SuppressionEntry(business_id=suppressed.id, reason="operator request", created_at=now),
            Job(
                job_type="GENERATE_DEMO",
                idempotency_key="failed-demo",
                status="failed",
                payload={"business_id": str(active.id)},
                created_at=now,
            ),
            Job(
                job_type="CALCULATE_SCORE",
                idempotency_key="not-eligible-score",
                status="not_eligible",
                payload={"business_id": str(active.id)},
                created_at=now,
            ),
        ]
    )
    session.commit()

    report = build_pilot_report(session, include_details=True)
    funnel = {item["stage"]: item["count"] for item in report["funnel_metrics"]}
    quality = {item["code"]: item["count"] for item in report["quality_metrics"]}
    workload = {(item["operator"], item["category"]): item["count"] for item in report["workload_metrics"]}
    assert funnel["MEETING"] == 1
    assert funnel["SUPPRESSED"] == 1
    assert quality["manual_outreach_logs"] == 1
    assert quality["system_delivery_count"] == 0
    assert quality["score_action:score_only"] == 1
    assert quality["job:GENERATE_DEMO:failed"] == 1
    assert quality["job:CALCULATE_SCORE:not_eligible"] == 1
    assert quality["crm_event:reply_received"] == 1
    assert workload[("operator", "manual_outreach")] == 1
    assert report["details"]["transitions"]["REPLIED->MEETING"] == 1
