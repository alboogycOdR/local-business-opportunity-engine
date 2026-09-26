"""Seed a deterministic, synthetic end-to-end pilot dataset.

This script only writes records marked by the ``sprint13-pilot`` campaign
policy. It never calls external providers or sends messages.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
from lboe_api.db import (  # noqa: E402
    AuditFinding,
    AuditRun,
    Business,
    BusinessBrief,
    BusinessBriefFact,
    BusinessBriefOpportunity,
    BusinessBriefRisk,
    Campaign,
    DemoArtifact,
    DemoQaRun,
    DemoReview,
    DemoReviewChecklistItem,
    GeneratedDemo,
    GeneratedDemoClaim,
    GeneratedDemoSection,
    Job,
    LeadCrmEvent,
    OpportunityComponent,
    OpportunityHold,
    OpportunityScore,
    OutreachChannelApproval,
    OutreachDraftCheck,
    OutreachDraftMessage,
    OutreachDraftPackage,
    OutreachExecutionRecord,
    OutreachReadinessCheck,
    OutreachReadinessReview,
    PipelineEvent,
    SourceObservation,
    SuppressionEntry,
    Website,
    make_session_factory,
)

SEED_KEY = "sprint13-pilot"
CHECKLIST = (
    "concept_banner_visible",
    "business_name_correct",
    "not_claiming_official_site",
    "no_fake_prices",
    "no_fake_testimonials",
    "no_unsupported_awards",
    "contact_links_safe",
    "source_claims_supported",
    "no_outreach_content",
    "appropriate_demo_type",
    "preview_opens_locally",
    "no_sensitive_or_prohibited_content",
)


def ident(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{SEED_KEY}:{label}")


def reset_synthetic(session) -> int:
    campaigns = session.scalars(select(Campaign).where(Campaign.policy["seed_key"].as_string() == SEED_KEY)).all()
    campaign_ids = [item.id for item in campaigns]
    if not campaign_ids:
        return 0
    business_ids = [
        item.id for item in session.scalars(select(Business).where(Business.campaign_id.in_(campaign_ids))).all()
    ]
    demos = session.scalars(select(GeneratedDemo).where(GeneratedDemo.business_id.in_(business_ids))).all()
    demo_ids = [item.id for item in demos]
    briefs = session.scalars(select(BusinessBrief).where(BusinessBrief.business_id.in_(business_ids))).all()
    brief_ids = [item.id for item in briefs]
    scores = session.scalars(select(OpportunityScore).where(OpportunityScore.business_id.in_(business_ids))).all()
    score_ids = [item.id for item in scores]
    packages = session.scalars(
        select(OutreachDraftPackage).where(OutreachDraftPackage.business_id.in_(business_ids))
    ).all()
    package_ids = [item.id for item in packages]
    readiness = session.scalars(
        select(OutreachReadinessReview).where(OutreachReadinessReview.business_id.in_(business_ids))
    ).all()
    readiness_ids = [item.id for item in readiness]
    ordered = [
        (LeadCrmEvent, LeadCrmEvent.business_id.in_(business_ids)),
        (OutreachExecutionRecord, OutreachExecutionRecord.business_id.in_(business_ids)),
        (OutreachChannelApproval, OutreachChannelApproval.outreach_readiness_review_id.in_(readiness_ids)),
        (OutreachReadinessCheck, OutreachReadinessCheck.outreach_readiness_review_id.in_(readiness_ids)),
        (OutreachReadinessReview, OutreachReadinessReview.business_id.in_(business_ids)),
        (OutreachDraftCheck, OutreachDraftCheck.package_id.in_(package_ids)),
        (OutreachDraftMessage, OutreachDraftMessage.package_id.in_(package_ids)),
        (OutreachDraftPackage, OutreachDraftPackage.business_id.in_(business_ids)),
        (
            DemoReviewChecklistItem,
            DemoReviewChecklistItem.demo_review_id.in_(
                select(DemoReview.id).where(DemoReview.business_id.in_(business_ids))
            ),
        ),
        (DemoReview, DemoReview.business_id.in_(business_ids)),
        (DemoArtifact, DemoArtifact.demo_id.in_(demo_ids)),
        (DemoQaRun, DemoQaRun.demo_id.in_(demo_ids)),
        (GeneratedDemoClaim, GeneratedDemoClaim.demo_id.in_(demo_ids)),
        (GeneratedDemoSection, GeneratedDemoSection.demo_id.in_(demo_ids)),
        (GeneratedDemo, GeneratedDemo.business_id.in_(business_ids)),
        (BusinessBriefRisk, BusinessBriefRisk.business_brief_id.in_(brief_ids)),
        (BusinessBriefOpportunity, BusinessBriefOpportunity.business_brief_id.in_(brief_ids)),
        (BusinessBriefFact, BusinessBriefFact.business_brief_id.in_(brief_ids)),
        (BusinessBrief, BusinessBrief.business_id.in_(business_ids)),
        (OpportunityHold, OpportunityHold.opportunity_score_id.in_(score_ids)),
        (OpportunityComponent, OpportunityComponent.opportunity_score_id.in_(score_ids)),
        (OpportunityScore, OpportunityScore.business_id.in_(business_ids)),
        (
            AuditFinding,
            AuditFinding.audit_run_id.in_(select(AuditRun.id).where(AuditRun.business_id.in_(business_ids))),
        ),
        (AuditRun, AuditRun.business_id.in_(business_ids)),
        (Website, Website.business_id.in_(business_ids)),
        (SourceObservation, SourceObservation.business_id.in_(business_ids)),
        (SuppressionEntry, SuppressionEntry.business_id.in_(business_ids)),
        (PipelineEvent, PipelineEvent.business_id.in_(business_ids)),
        (Job, Job.payload["business_id"].as_string().in_([str(item) for item in business_ids])),
        (Business, Business.id.in_(business_ids)),
        (Campaign, Campaign.id.in_(campaign_ids)),
    ]
    for model, predicate in ordered:
        session.execute(delete(model).where(predicate))
    session.commit()
    return len(campaign_ids)


def seed(database_url: str, reset: bool = False) -> dict[str, str | int]:
    session = make_session_factory(database_url)()
    if reset:
        reset_synthetic(session)
    campaign_id = ident("campaign")
    campaign = session.get(Campaign, campaign_id)
    if campaign is not None and not reset:
        existing_demo = session.get(GeneratedDemo, ident("demo"))
        existing_package = session.get(OutreachDraftPackage, ident("package"))
        existing_execution = session.get(OutreachExecutionRecord, ident("execution"))
        return {
            "campaign_id": str(campaign.id),
            "demo_business_id": str(ident("demo")),
            "score_only_business_id": str(ident("score-only")),
            "suppressed_business_id": str(ident("suppressed")),
            "ambiguous_business_id": str(ident("ambiguous")),
            "contacted_business_id": str(ident("contacted")),
            "demo_id": str(existing_demo.id) if existing_demo else str(ident("demo")),
            "outreach_draft_package_id": str(existing_package.id) if existing_package else str(ident("package")),
            "outreach_log_id": str(existing_execution.id) if existing_execution else str(ident("execution")),
        }
    if campaign is None:
        campaign = Campaign(
            id=campaign_id,
            name="Cape Town Hair Salon Pilot (Synthetic)",
            vertical="hair_salon",
            geography="Cape Town",
            policy={"synthetic": True, "seed_key": SEED_KEY, "no_external_calls": True},
        )
        session.add(campaign)
        session.flush()
    now = datetime.now(UTC)

    def business(key: str, name: str, state: str) -> Business:
        item = session.get(Business, ident(key))
        if item is None:
            item = Business(
                id=ident(key),
                campaign_id=campaign.id,
                display_name=name,
                category="hair salon",
                locality="Cape Town",
                address_text="Synthetic Cape Town",
                identity_key=f"{SEED_KEY}:{key}",
                state=state,
            )
            session.add(item)
        return item

    demo_business = business("demo", "Synthetic Starter Salon", "MEETING")
    score_only = business("score-only", "Synthetic Healthy Salon", "SCORED")
    suppressed = business("suppressed", "Synthetic Suppressed Salon", "SUPPRESSED")
    ambiguous = business("ambiguous", "Synthetic Ambiguous Salon", "DISCOVERED")
    contacted = business("contacted", "Synthetic Contacted Salon", "CONTACTED")
    session.flush()

    score = OpportunityScore(
        id=ident("score"),
        business_id=demo_business.id,
        version="opportunity-v1",
        score=84,
        band="high",
        recommended_next_action="generate_demo",
    )
    session.add(score)
    session.flush()
    brief = BusinessBrief(
        id=ident("brief"),
        business_id=demo_business.id,
        score_id=score.id,
        version="brief-v1",
        summary="Synthetic facts support a starter concept demo.",
        recommended_next_action="generate_demo",
        confidence=0.95,
    )
    session.add(brief)
    session.flush()
    session.add(
        BusinessBriefFact(
            business_brief_id=brief.id,
            fact_type="identity",
            label="Business name",
            value=demo_business.display_name,
            source_type="manual",
            evidence={"synthetic": True},
            confidence=1.0,
        )
    )
    session.add(
        BusinessBriefFact(
            business_brief_id=brief.id,
            fact_type="identity",
            label="Category",
            value="hair salon",
            source_type="manual",
            evidence={"synthetic": True},
            confidence=1.0,
        )
    )
    session.add(
        BusinessBriefOpportunity(
            business_brief_id=brief.id,
            code="NO_WEBSITE",
            title="Starter website opportunity",
            description="No website was verified in the synthetic pilot.",
            priority="high",
            evidence={"synthetic": True},
        )
    )
    demo = GeneratedDemo(
        id=ident("demo"),
        business_id=demo_business.id,
        brief_id=brief.id,
        score_id=score.id,
        version="demo-v1",
        demo_type="starter_website",
        status="approved",
        preview_path=str(ROOT / "artifacts" / "demos" / str(ident("demo")) / "index.html"),
    )
    session.add(demo)
    session.flush()
    session.add(
        GeneratedDemoSection(
            demo_id=demo.id,
            section_type="hero",
            heading=demo_business.display_name,
            body="Independent concept preview.",
            sort_order=1,
            evidence={"synthetic": True},
        )
    )
    session.add(
        GeneratedDemoClaim(
            demo_id=demo.id,
            claim_text="Independent concept preview",
            claim_type="disclaimer",
            evidence={"synthetic": True},
            confidence=1.0,
            approved=True,
        )
    )
    artifact_dir = ROOT / "artifacts" / "demos" / str(demo.id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "index.html": "<html><body>Concept preview prepared independently for demonstration.</body></html>",
        "styles.css": "body{font-family:sans-serif}",
        "metadata.json": json.dumps({"synthetic": True}),
    }
    for name, content in files.items():
        path = artifact_dir / name
        path.write_text(content, encoding="utf-8")
        session.add(
            DemoArtifact(
                demo_id=demo.id,
                kind=name.rsplit(".", 1)[0],
                path=str(path),
                mime_type="text/html" if name.endswith("html") else "text/plain",
                byte_size=path.stat().st_size,
            )
        )
    session.add(DemoQaRun(demo_id=demo.id, status="passed", checks={"synthetic": True}))
    review = DemoReview(
        id=ident("review"),
        demo_id=demo.id,
        business_id=demo_business.id,
        decision="approve",
        reviewer="seed-operator",
        notes="Synthetic pilot approval",
        resulting_demo_status="approved",
        resulting_business_state="APPROVED_FOR_OUTREACH",
    )
    session.add(review)
    session.flush()
    for code in CHECKLIST:
        session.add(
            DemoReviewChecklistItem(demo_review_id=review.id, code=code, label=code.replace("_", " "), passed=True)
        )
    package = OutreachDraftPackage(
        id=ident("package"),
        business_id=demo_business.id,
        demo_id=demo.id,
        brief_id=brief.id,
        score_id=score.id,
        version="outreach-v1",
        offer_type="starter_website_offer",
        offer_angle="Independent concept preview",
        status="ready",
    )
    session.add(package)
    session.flush()
    messages = []
    for channel in ("email", "whatsapp", "phone_script", "manual_note"):
        msg = OutreachDraftMessage(
            id=ident(f"message:{channel}"),
            package_id=package.id,
            channel=channel,
            subject="Independent concept preview",
            body="I prepared an independent concept preview for your review.",
            tone="neutral",
            evidence={"synthetic": True},
            approved=channel == "email",
        )
        messages.append(msg)
        session.add(msg)
    session.add(
        OutreachDraftCheck(package_id=package.id, code="concept_disclaimer", passed=True, evidence={"synthetic": True})
    )
    readiness = OutreachReadinessReview(
        id=ident("readiness"),
        business_id=demo_business.id,
        outreach_draft_package_id=package.id,
        decision="approve_for_manual_outreach",
        reviewer="seed-operator",
        notes="Synthetic manual readiness",
        consent_basis_type="public_business_contact_for_manual_outreach",
        consent_basis_notes="Synthetic only.",
        resulting_business_state="OUTREACH_READY",
    )
    session.add(readiness)
    session.flush()
    session.add(
        OutreachChannelApproval(
            outreach_readiness_review_id=readiness.id,
            channel="email",
            outreach_draft_message_id=messages[0].id,
            approved=True,
        )
    )
    session.add(
        OutreachReadinessCheck(
            outreach_readiness_review_id=readiness.id,
            code="no_sending_performed",
            passed=True,
            evidence={"synthetic": True},
        )
    )
    execution = OutreachExecutionRecord(
        id=ident("execution"),
        business_id=demo_business.id,
        outreach_draft_package_id=package.id,
        outreach_draft_message_id=messages[0].id,
        channel="email",
        operator="seed-operator",
        sent_at=now,
        external_reference="synthetic-no-send",
        notes="Operator log only; no system delivery.",
        evidence={"synthetic": True},
        resulting_business_state="CONTACTED",
    )
    session.add(execution)
    session.flush()
    session.add(
        LeadCrmEvent(
            id=ident("reply"),
            business_id=demo_business.id,
            outreach_execution_record_id=execution.id,
            event_type="reply_received",
            channel="email",
            operator="seed-operator",
            occurred_at=now,
            summary="Synthetic reply",
            resulting_business_state="REPLIED",
        )
    )
    session.add(
        LeadCrmEvent(
            id=ident("meeting"),
            business_id=demo_business.id,
            outreach_execution_record_id=execution.id,
            event_type="meeting_scheduled",
            channel="email",
            operator="seed-operator",
            occurred_at=now,
            summary="Synthetic meeting",
            resulting_business_state="MEETING",
        )
    )
    session.add(
        OpportunityScore(
            id=ident("score-only-score"),
            business_id=score_only.id,
            version="opportunity-v1",
            score=18,
            band="low",
            recommended_next_action="score_only",
        )
    )
    session.add(
        SuppressionEntry(id=ident("suppression"), business_id=suppressed.id, reason="Synthetic suppression test")
    )
    session.add(
        Job(
            id=ident("job-not-eligible"),
            idempotency_key=f"{SEED_KEY}:score-only",
            job_type="GENERATE_DEMO",
            status="not_eligible",
            payload={"business_id": str(score_only.id)},
        )
    )
    session.add(
        PipelineEvent(
            business_id=demo_business.id,
            from_state="OUTREACH_READY",
            to_state="CONTACTED",
            actor="seed",
            reason="synthetic manual log",
        )
    )
    session.add(
        PipelineEvent(
            business_id=demo_business.id,
            from_state="CONTACTED",
            to_state="REPLIED",
            actor="seed",
            reason="synthetic CRM event",
        )
    )
    session.add(
        PipelineEvent(
            business_id=demo_business.id,
            from_state="REPLIED",
            to_state="MEETING",
            actor="seed",
            reason="synthetic CRM event",
        )
    )
    session.add(
        SourceObservation(
            business_id=demo_business.id,
            field="display_name",
            source_type="manual",
            source_ref="sprint13",
            storage_policy="persistent",
            confidence=1.0,
            value=demo_business.display_name,
        )
    )
    session.add(
        SourceObservation(
            business_id=score_only.id,
            field="display_name",
            source_type="manual",
            source_ref="sprint13",
            storage_policy="persistent",
            confidence=1.0,
            value=score_only.display_name,
        )
    )
    session.commit()
    return {
        "campaign_id": str(campaign.id),
        "demo_business_id": str(demo_business.id),
        "score_only_business_id": str(score_only.id),
        "suppressed_business_id": str(suppressed.id),
        "ambiguous_business_id": str(ambiguous.id),
        "contacted_business_id": str(contacted.id),
        "demo_id": str(demo.id),
        "outreach_draft_package_id": str(package.id),
        "outreach_log_id": str(execution.id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("LBOE_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe",
    )
    parser.add_argument("--reset-synthetic", action="store_true")
    args = parser.parse_args()
    result = seed(args.database_url, args.reset_synthetic)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
