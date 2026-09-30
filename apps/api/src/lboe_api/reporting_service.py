"""Live, deterministic pilot reporting over the system-of-record tables."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import func, select
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
    ProposalExport,
    ProposalPackage,
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
    campaigns = session.execute(select(Campaign.id, Campaign.vertical))
    campaign_map = {campaign_id: campaign_vertical for campaign_id, campaign_vertical in campaigns}
    if campaign_id is not None:
        if campaign_id not in campaign_map:
            raise ValueError("campaign_not_found")
        selected_campaign_ids = {campaign_id}
    else:
        selected_campaign_ids = {
            item_id for item_id, item_vertical in campaign_map.items() if vertical is None or item_vertical == vertical
        }
    campaign_ids = list(selected_campaign_ids)
    business_scope = select(Business.id).where(Business.campaign_id.in_(campaign_ids))
    if start is not None:
        business_scope = business_scope.where(Business.created_at >= start)
    if end is not None:
        business_scope = business_scope.where(Business.created_at <= end)
    business_ids = business_scope

    def within(column: Any) -> list[Any]:
        clauses: list[Any] = []
        if start is not None:
            clauses.append(column >= start)
        if end is not None:
            clauses.append(column <= end)
        return clauses

    def total(query: Any) -> int:
        return int(session.scalar(query) or 0)

    def grouped(query: Any) -> dict[Any, int]:
        return {key: int(value) for key, value in session.execute(query).all()}

    def scoped(model: Any, timestamp: Any, *extra: Any) -> Any:
        return (
            select(model)
            .join(Business, model.business_id == Business.id)
            .where(Business.id.in_(business_ids), *within(timestamp), *extra)
        )

    def scoped_group(model: Any, timestamp: Any, key: Any, *extra: Any) -> dict[Any, int]:
        return grouped(
            select(key, func.count())
            .select_from(model)
            .join(Business, model.business_id == Business.id)
            .where(Business.id.in_(business_ids), *within(timestamp), *extra)
            .group_by(key)
        )

    business_count = total(select(func.count()).select_from(business_ids.subquery()))
    funnel_counts = {stage: 0 for stage in STAGES}
    funnel_counts.update(
        grouped(
            select(Business.state, func.count())
            .where(Business.id.in_(business_ids), *within(Business.created_at))
            .group_by(Business.state)
        )
    )
    funnel = [{"stage": stage, "count": funnel_counts[stage]} for stage in STAGES]
    transition_pairs = session.execute(
        select(PipelineEvent.from_state, PipelineEvent.to_state, func.count())
        .select_from(PipelineEvent)
        .join(Business, PipelineEvent.business_id == Business.id)
        .where(Business.id.in_(business_ids), *within(PipelineEvent.created_at))
        .group_by(PipelineEvent.from_state, PipelineEvent.to_state)
    ).all()
    transitions = Counter({f"{before or 'NONE'}->{after}": int(count) for before, after, count in transition_pairs})
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

    candidate_status = grouped(
        select(DiscoveryCandidate.status, func.count())
        .where(DiscoveryCandidate.campaign_id.in_(campaign_ids), *within(DiscoveryCandidate.created_at))
        .group_by(DiscoveryCandidate.status)
    )
    duplicate_count = total(
        select(func.count())
        .select_from(DedupeEvidence)
        .where(
            DedupeEvidence.campaign_id.in_(campaign_ids),
            DedupeEvidence.merged.is_(True),
            *within(DedupeEvidence.created_at),
        )
    )
    observation_count = total(
        select(func.count())
        .select_from(SourceObservation)
        .join(Business, SourceObservation.business_id == Business.id)
        .where(Business.id.in_(business_ids), *within(SourceObservation.observed_at))
    )
    identity_count = total(
        select(func.count())
        .select_from(BusinessExternalIdentity)
        .join(Business, BusinessExternalIdentity.business_id == Business.id)
        .where(Business.id.in_(business_ids), *within(BusinessExternalIdentity.observed_at))
    )
    audit_count = total(scoped(AuditRun, AuditRun.started_at).with_only_columns(func.count()))
    audit_finding_counts = grouped(
        select(AuditFinding.code, func.count())
        .select_from(AuditFinding)
        .join(AuditRun, AuditFinding.audit_run_id == AuditRun.id)
        .join(Business, AuditRun.business_id == Business.id)
        .where(
            Business.id.in_(business_ids),
            *within(AuditRun.started_at),
            *within(AuditFinding.observed_at),
        )
        .group_by(AuditFinding.code)
    )
    score_bands = scoped_group(OpportunityScore, OpportunityScore.created_at, OpportunityScore.band)
    score_actions = scoped_group(
        OpportunityScore, OpportunityScore.created_at, OpportunityScore.recommended_next_action
    )
    average_score = session.scalar(
        select(func.avg(OpportunityScore.score))
        .select_from(OpportunityScore)
        .join(Business, OpportunityScore.business_id == Business.id)
        .where(Business.id.in_(business_ids), *within(OpportunityScore.created_at))
    )
    demo_statuses = scoped_group(GeneratedDemo, GeneratedDemo.created_at, GeneratedDemo.status)
    qa_statuses = grouped(
        select(DemoQaRun.status, func.count())
        .select_from(DemoQaRun)
        .join(GeneratedDemo, DemoQaRun.demo_id == GeneratedDemo.id)
        .join(Business, GeneratedDemo.business_id == Business.id)
        .where(
            Business.id.in_(business_ids),
            *within(GeneratedDemo.created_at),
            *within(DemoQaRun.created_at),
        )
        .group_by(DemoQaRun.status)
    )
    package_statuses = scoped_group(OutreachDraftPackage, OutreachDraftPackage.created_at, OutreachDraftPackage.status)
    review_count = total(
        scoped(OutreachReadinessReview, OutreachReadinessReview.created_at).with_only_columns(func.count())
    )
    demo_reviewers = scoped_group(DemoReview, DemoReview.created_at, DemoReview.reviewer)
    readiness_reviewers = scoped_group(
        OutreachReadinessReview, OutreachReadinessReview.created_at, OutreachReadinessReview.reviewer
    )
    execution_operators = scoped_group(
        OutreachExecutionRecord, OutreachExecutionRecord.sent_at, OutreachExecutionRecord.operator
    )
    crm_operators = scoped_group(LeadCrmEvent, LeadCrmEvent.occurred_at, LeadCrmEvent.operator)
    approved_channels = grouped(
        select(OutreachChannelApproval.channel, func.count())
        .select_from(OutreachChannelApproval)
        .join(
            OutreachReadinessReview,
            OutreachChannelApproval.outreach_readiness_review_id == OutreachReadinessReview.id,
        )
        .join(Business, OutreachReadinessReview.business_id == Business.id)
        .where(
            Business.id.in_(business_ids),
            *within(OutreachReadinessReview.created_at),
            OutreachChannelApproval.approved.is_(True),
        )
        .group_by(OutreachChannelApproval.channel)
    )
    execution_channels = scoped_group(
        OutreachExecutionRecord, OutreachExecutionRecord.sent_at, OutreachExecutionRecord.channel
    )
    crm_types = scoped_group(LeadCrmEvent, LeadCrmEvent.occurred_at, LeadCrmEvent.event_type)
    proposal_statuses = scoped_group(ProposalPackage, ProposalPackage.created_at, ProposalPackage.status)
    proposal_scope = (
        select(ProposalPackage.id)
        .join(Business, ProposalPackage.business_id == Business.id)
        .where(Business.id.in_(business_ids), *within(ProposalPackage.created_at))
    )
    export_count = total(
        select(func.count()).select_from(ProposalExport).where(ProposalExport.proposal_id.in_(proposal_scope))
    )
    brief_scope = (
        select(BusinessBrief.id)
        .join(Business, BusinessBrief.business_id == Business.id)
        .where(Business.id.in_(business_ids), *within(BusinessBrief.created_at))
    )
    brief_count = total(select(func.count()).select_from(brief_scope.subquery()))
    risk_counts = grouped(
        select(BusinessBriefRisk.code, func.count())
        .where(BusinessBriefRisk.business_brief_id.in_(brief_scope))
        .group_by(BusinessBriefRisk.code)
    )
    suppression_count = total(scoped(SuppressionEntry, SuppressionEntry.created_at).with_only_columns(func.count()))
    missing_website_count = total(
        select(func.count())
        .select_from(Business)
        .where(
            Business.id.in_(business_ids),
            ~select(Website.business_id)
            .where(Website.business_id == Business.id, *within(Website.checked_at))
            .exists(),
        )
    )
    business_id_strings = sorted({str(value) for value in session.scalars(business_ids).all()})
    job_counts: Counter[tuple[str, str]] = Counter()
    for offset in range(0, len(business_id_strings), 5000):
        job_counts.update(
            {
                (job_type, status): int(count)
                for job_type, status, count in session.execute(
                    select(Job.job_type, Job.status, func.count())
                    .where(
                        Job.status.in_(["failed", "not_eligible"]),
                        *within(Job.created_at),
                        Job.payload["business_id"].as_string().in_(business_id_strings[offset : offset + 5000]),
                    )
                    .group_by(Job.job_type, Job.status)
                ).all()
            }
        )

    report_vertical = campaign_map[campaign_id] if campaign_id is not None else vertical
    quality: list[dict[str, Any]] = [
        {"code": "businesses_discovered", "count": business_count},
        {"code": "duplicates", "count": duplicate_count},
        {"code": "ambiguous_candidates", "count": candidate_status.get("ambiguous", 0)},
        {
            "code": "unresolved_candidates",
            "count": candidate_status.get("ambiguous", 0) + candidate_status.get("unresolved", 0),
        },
        {"code": "source_observations", "count": observation_count},
        {"code": "external_identities", "count": identity_count},
        {"code": "audit_runs", "count": audit_count},
        {"code": "website_healthy", "count": audit_finding_counts.get("WEBSITE_HEALTHY", 0)},
        {"code": "website_unreachable", "count": audit_finding_counts.get("WEBSITE_UNREACHABLE", 0)},
        {
            "code": "website_missing",
            "count": audit_finding_counts.get("WEBSITE_MISSING", 0) + missing_website_count,
        },
        {"code": "score_count", "count": sum(score_bands.values())},
        {"code": "brief_count", "count": brief_count},
        {"code": "average_score", "count": round(float(average_score), 2) if average_score is not None else 0},
        {"code": "demo_generated", "count": sum(demo_statuses.values())},
        {"code": "demo_qa_passed", "count": qa_statuses.get("passed", 0)},
        {"code": "demo_qa_failed", "count": qa_statuses.get("failed", 0)},
        {"code": "approved_demos", "count": demo_statuses.get("approved", 0)},
        {"code": "outreach_drafts_ready", "count": package_statuses.get("ready", 0)},
        {"code": "outreach_drafts_blocked", "count": package_statuses.get("blocked", 0)},
        {"code": "readiness_reviews", "count": review_count},
        {"code": "manual_outreach_logs", "count": sum(execution_channels.values())},
        {"code": "system_delivery_count", "count": 0},
        {"code": "proposal_packages_created", "count": sum(proposal_statuses.values())},
        {"code": "proposal_approved", "count": proposal_statuses.get("approved", 0)},
        {"code": "proposal_exported", "count": export_count},
        {
            "code": "proposal_ready_queue_count",
            "count": proposal_statuses.get("draft", 0) + proposal_statuses.get("changes_requested", 0),
        },
        {"code": "suppression_entries", "count": suppression_count},
        {"code": "do_not_contact_holds", "count": risk_counts.get("DO_NOT_CONTACT", 0)},
    ]
    quality.extend({"code": f"score_band:{key}", "count": value} for key, value in sorted(score_bands.items()))
    quality.extend({"code": f"score_action:{key}", "count": value} for key, value in sorted(score_actions.items()))
    quality.extend(
        {"code": f"audit_finding:{key}", "count": value} for key, value in sorted(audit_finding_counts.items())
    )
    quality.extend({"code": f"crm_event:{key}", "count": value} for key, value in sorted(crm_types.items()))
    quality.extend(
        {"code": f"job:{job_type}:{status}", "count": count} for (job_type, status), count in sorted(job_counts.items())
    )
    quality.extend(
        {"code": f"selected_channel:{key}", "count": value} for key, value in sorted(approved_channels.items())
    )
    quality.extend(
        {"code": f"execution_channel:{key}", "count": value} for key, value in sorted(execution_channels.items())
    )

    workload_counter: Counter[tuple[str, str]] = Counter()
    workload_counter.update({(operator, "demo_review"): count for operator, count in demo_reviewers.items()})
    workload_counter.update({(operator, "readiness_review"): count for operator, count in readiness_reviewers.items()})
    workload_counter.update({(operator, "manual_outreach"): count for operator, count in execution_operators.items()})
    workload_counter.update({(operator, "crm_event"): count for operator, count in crm_operators.items()})
    workload = [
        {"operator": operator, "category": category, "count": count}
        for (operator, category), count in sorted(workload_counter.items())
    ]
    warnings = []
    if not business_count:
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
            "common_audit_findings": dict(
                sorted(audit_finding_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:20]
            ),
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


def dashboard_metrics(session: Session) -> dict[str, Any]:
    """The handful of counts the operator dashboard shows, computed with SQL COUNTs.

    Same funnel shape as ``build_pilot_report`` (all campaigns, no date window) without
    materialising every operational row on each dashboard load.
    """
    by_state: dict[str, int] = {
        state: int(total)
        for state, total in session.execute(select(Business.state, func.count()).group_by(Business.state)).all()
    }
    funnel = [{"stage": stage, "count": int(by_state.get(stage, 0))} for stage in STAGES]

    def count(model: Any, *where: Any) -> int:
        return int(session.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    quality = [
        {"code": "system_delivery_count", "count": 0},
        {"code": "jobs_failed_or_not_eligible", "count": count(Job, Job.status.in_(["failed", "not_eligible"]))},
        {"code": "approved_demos", "count": count(GeneratedDemo, GeneratedDemo.status == "approved")},
        {
            "code": "proposal_ready_queue_count",
            "count": count(ProposalPackage, ProposalPackage.status.in_(["draft", "changes_requested"])),
        },
    ]
    return {"funnel_metrics": funnel, "quality_metrics": quality}
