"""Live, deterministic pilot reporting over the system-of-record tables."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import (
    AuditFinding,
    AuditRun,
    Business,
    BusinessBrief,
    BusinessBriefRisk,
    BusinessExternalIdentity,
    Campaign,
    DedupeEvidence,
    DemoQaRun,
    DemoReview,
    DiscoveryCandidate,
    GeneratedDemo,
    Job,
    LeadCrmEvent,
    OpportunityScore,
    OutreachChannelApproval,
    OutreachDraftPackage,
    OutreachExecutionRecord,
    OutreachReadinessReview,
    PipelineEvent,
    SourceObservation,
    SuppressionEntry,
    Website,
)

STAGES = (
    "DISCOVERED",
    "DEDUPED",
    "QUALIFIED",
    "ENRICHED",
    "AUDITED",
    "SCORED",
    "DEMO_GENERATED",
    "REVIEW_PENDING",
    "APPROVED_FOR_OUTREACH",
    "CONSENT_PENDING",
    "OUTREACH_READY",
    "CONTACTED",
    "REPLIED",
    "MEETING",
    "PROPOSAL",
    "WON",
    "LOST",
    "SUPPRESSED",
    "ARCHIVED",
)


def _in_window(value: datetime | None, start: datetime | None, end: datetime | None) -> bool:
    if value is None:
        return False
    stamp = value if value.tzinfo else value.replace(tzinfo=UTC)
    return (start is None or stamp >= start) and (end is None or stamp <= end)


def _bounds(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(start_date, time.min, tzinfo=UTC) if start_date else None
    end = datetime.combine(end_date, time.max, tzinfo=UTC) if end_date else None
    return start, end


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def build_pilot_report(
    session: Session,
    *,
    campaign_id: Any = None,
    vertical: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    start, end = _bounds(start_date, end_date)
    campaigns = session.scalars(select(Campaign)).all()
    campaign_map = {item.id: item for item in campaigns}
    if campaign_id is not None:
        campaign = campaign_map.get(campaign_id)
        if campaign is None:
            raise ValueError("campaign_not_found")
        selected_campaign_ids = {campaign_id}
    else:
        selected_campaign_ids = {item.id for item in campaigns if vertical is None or item.vertical == vertical}
    businesses = [
        item
        for item in session.scalars(select(Business)).all()
        if item.campaign_id in selected_campaign_ids and _in_window(item.created_at, start, end)
    ]
    business_ids = {item.id for item in businesses}
    report_vertical: str | None
    if vertical is None and campaign_id is not None:
        report_vertical = campaign_map[campaign_id].vertical
    elif campaign_id is not None:
        report_vertical = campaign_map[campaign_id].vertical
    else:
        report_vertical = vertical

    events = [
        item
        for item in session.scalars(select(PipelineEvent)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    funnel_counts: dict[str, int] = {stage: sum(1 for item in businesses if item.state == stage) for stage in STAGES}
    funnel = [{"stage": stage, "count": funnel_counts[stage]} for stage in STAGES]
    transitions = Counter(f"{item.from_state or 'NONE'}->{item.to_state}" for item in events)
    transition_map = {
        "discovered_to_deduped": ("DISCOVERED->DEDUPED", "DISCOVERED"),
        "deduped_to_qualified": ("DEDUPED->QUALIFIED", "DEDUPED"),
        "contacted_to_replied": ("CONTACTED->REPLIED", "CONTACTED"),
        "replied_to_meeting": ("REPLIED->MEETING", "REPLIED"),
        "meeting_to_proposal": ("MEETING->PROPOSAL", "MEETING"),
        "proposal_to_won": ("PROPOSAL->WON", "PROPOSAL"),
    }
    conversions = [
        {
            "code": code,
            "numerator": transitions.get(key, 0),
            "denominator": funnel_counts.get(stage, 0),
            "rate": _rate(transitions.get(key, 0), funnel_counts.get(stage, 0)),
        }
        for code, (key, stage) in transition_map.items()
    ]

    candidates = [
        item
        for item in session.scalars(select(DiscoveryCandidate)).all()
        if item.campaign_id in selected_campaign_ids and _in_window(item.created_at, start, end)
    ]
    dedupe = [
        item
        for item in session.scalars(select(DedupeEvidence)).all()
        if item.campaign_id in selected_campaign_ids and _in_window(item.created_at, start, end)
    ]
    observations = [
        item
        for item in session.scalars(select(SourceObservation)).all()
        if item.business_id in business_ids and _in_window(item.observed_at, start, end)
    ]
    identities = [
        item
        for item in session.scalars(select(BusinessExternalIdentity)).all()
        if item.business_id in business_ids and _in_window(item.observed_at, start, end)
    ]
    audits = [
        item
        for item in session.scalars(select(AuditRun)).all()
        if item.business_id in business_ids and _in_window(item.started_at, start, end)
    ]
    websites = [
        item
        for item in session.scalars(select(Website)).all()
        if item.business_id in business_ids and _in_window(item.checked_at, start, end)
    ]
    audit_ids = {item.id for item in audits}
    findings = [
        item
        for item in session.scalars(select(AuditFinding)).all()
        if item.audit_run_id in audit_ids and _in_window(item.observed_at, start, end)
    ]
    scores = [
        item
        for item in session.scalars(select(OpportunityScore)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    demos = [
        item
        for item in session.scalars(select(GeneratedDemo)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    qa_runs = [
        item
        for item in session.scalars(select(DemoQaRun)).all()
        if item.demo_id in {demo.id for demo in demos} and _in_window(item.created_at, start, end)
    ]
    reviews = [
        item
        for item in session.scalars(select(DemoReview)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    packages = [
        item
        for item in session.scalars(select(OutreachDraftPackage)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    readiness = [
        item
        for item in session.scalars(select(OutreachReadinessReview)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    channel_approvals = [
        item
        for item in session.scalars(select(OutreachChannelApproval)).all()
        if item.outreach_readiness_review_id in {review.id for review in readiness}
    ]
    executions = [
        item
        for item in session.scalars(select(OutreachExecutionRecord)).all()
        if item.business_id in business_ids and _in_window(item.sent_at, start, end)
    ]
    crm_events = [
        item
        for item in session.scalars(select(LeadCrmEvent)).all()
        if item.business_id in business_ids and _in_window(item.occurred_at, start, end)
    ]
    suppressions = [
        item
        for item in session.scalars(select(SuppressionEntry)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    ]
    brief_ids = {
        item.id
        for item in session.scalars(select(BusinessBrief)).all()
        if item.business_id in business_ids and _in_window(item.created_at, start, end)
    }
    risks = [item for item in session.scalars(select(BusinessBriefRisk)).all() if item.business_brief_id in brief_ids]
    jobs = [
        item
        for item in session.scalars(select(Job)).all()
        if _in_window(item.created_at, start, end)
        and str(item.payload.get("business_id")) in {str(x) for x in business_ids}
    ]

    finding_counts = Counter(item.code for item in findings)
    score_actions = Counter(item.recommended_next_action for item in scores)
    score_bands = Counter(item.band for item in scores)
    crm_counts = Counter(item.event_type for item in crm_events)
    quality: list[dict[str, Any]] = [
        {"code": "businesses_discovered", "count": len(businesses)},
        {"code": "duplicates", "count": sum(1 for item in dedupe if item.merged)},
        {"code": "ambiguous_candidates", "count": sum(1 for item in candidates if item.status == "ambiguous")},
        {
            "code": "unresolved_candidates",
            "count": sum(1 for item in candidates if item.status in {"ambiguous", "unresolved"}),
        },
        {"code": "source_observations", "count": len(observations)},
        {"code": "external_identities", "count": len(identities)},
        {"code": "audit_runs", "count": len(audits)},
        {"code": "website_healthy", "count": finding_counts.get("WEBSITE_HEALTHY", 0)},
        {"code": "website_unreachable", "count": finding_counts.get("WEBSITE_UNREACHABLE", 0)},
        {
            "code": "website_missing",
            "count": finding_counts.get("WEBSITE_MISSING", 0)
            + sum(1 for item in businesses if item.id not in {website.business_id for website in websites}),
        },
        {"code": "score_count", "count": len(scores)},
        {"code": "average_score", "count": round(sum(item.score for item in scores) / len(scores), 2) if scores else 0},
        {"code": "demo_generated", "count": len(demos)},
        {"code": "demo_qa_passed", "count": sum(1 for item in qa_runs if item.status == "passed")},
        {"code": "demo_qa_failed", "count": sum(1 for item in qa_runs if item.status == "failed")},
        {"code": "approved_demos", "count": sum(1 for item in demos if item.status == "approved")},
        {"code": "outreach_drafts_ready", "count": sum(1 for item in packages if item.status == "ready")},
        {"code": "outreach_drafts_blocked", "count": sum(1 for item in packages if item.status == "blocked")},
        {"code": "readiness_reviews", "count": len(readiness)},
        {"code": "manual_outreach_logs", "count": len(executions)},
        {"code": "system_delivery_count", "count": 0},
        {"code": "suppression_entries", "count": len(suppressions)},
        {"code": "do_not_contact_holds", "count": sum(1 for item in risks if item.code == "DO_NOT_CONTACT")},
    ]
    quality.extend({"code": f"score_band:{key}", "count": value} for key, value in sorted(score_bands.items()))
    quality.extend({"code": f"score_action:{key}", "count": value} for key, value in sorted(score_actions.items()))
    quality.extend({"code": f"audit_finding:{key}", "count": value} for key, value in sorted(finding_counts.items()))
    quality.extend({"code": f"crm_event:{key}", "count": value} for key, value in sorted(crm_counts.items()))
    job_counts = Counter((item.job_type, item.status) for item in jobs if item.status in {"failed", "not_eligible"})
    quality.extend(
        {"code": f"job:{job_type}:{status}", "count": count} for (job_type, status), count in sorted(job_counts.items())
    )
    channel_counts = Counter(item.channel for item in channel_approvals if item.approved)
    quality.extend({"code": f"selected_channel:{key}", "count": value} for key, value in sorted(channel_counts.items()))
    quality.extend(
        {"code": f"execution_channel:{key}", "count": value}
        for key, value in sorted(Counter(item.channel for item in executions).items())
    )

    workload_counter: Counter[tuple[str, str]] = Counter()
    workload_counter.update((item.reviewer, "demo_review") for item in reviews)
    workload_counter.update((item.reviewer, "readiness_review") for item in readiness)
    workload_counter.update((item.operator, "manual_outreach") for item in executions)
    workload_counter.update((item.operator, "crm_event") for item in crm_events)
    workload = [
        {"operator": operator, "category": category, "count": count}
        for (operator, category), count in sorted(workload_counter.items())
    ]
    warnings = []
    if not businesses:
        warnings.append("No businesses matched the selected filters.")
    limitations = [
        "Metrics are computed live from append-only operational tables.",
        "Manual outreach logs represent operator assertions; system delivery is always zero.",
        "Current funnel counts reflect current business state, while transition metrics use recorded events.",
    ]
    details: dict[str, Any] = {}
    if include_details:
        details = {
            "transitions": dict(sorted(transitions.items())),
            "jobs_failed_or_not_eligible": {f"{key[0]}:{key[1]}": value for key, value in sorted(job_counts.items())},
            "common_audit_findings": dict(finding_counts.most_common(20)),
        }
    return {
        "campaign_id": campaign_id,
        "vertical": report_vertical,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": datetime.now(UTC),
        "funnel_metrics": funnel,
        "conversion_metrics": conversions,
        "quality_metrics": quality,
        "workload_metrics": workload,
        "warnings": warnings,
        "limitations": limitations,
        "details": details,
    }
