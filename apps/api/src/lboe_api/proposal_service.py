"""Deterministic, evidence-backed proposal pack generation and export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from lboe_domain import LeadState
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import (
    Business,
    BusinessBrief,
    BusinessBriefRisk,
    GeneratedDemo,
    LeadCrmEvent,
    OpportunityScore,
    ProposalAssumption,
    ProposalExport,
    ProposalLineItem,
    ProposalPackage,
    ProposalSection,
)

VERSION = "proposal-v1"
BLOCKED = {
    "suppressed",
    "do_not_contact",
    "ambiguous_identity",
    "insufficient_evidence",
    "no_interest",
    "brief_required",
    "score_required",
    "no_approved_demo",
}


def _evidence(brief: BusinessBrief | None, score: OpportunityScore | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if brief:
        out.append(
            {
                "source_type": "business_brief",
                "source_id": str(brief.id),
                "description": "Deterministic business brief",
                "confidence": brief.confidence,
            }
        )
    if score:
        out.append(
            {
                "source_type": "opportunity_score",
                "source_id": str(score.id),
                "description": f"Score {score.score} ({score.band})",
                "confidence": 1.0,
            }
        )
    return out


def eligibility(
    session: Session, business: Business, operator_requested: bool = False
) -> tuple[bool, str | None, BusinessBrief | None, OpportunityScore | None, GeneratedDemo | None]:
    brief = session.scalar(
        select(BusinessBrief).where(BusinessBrief.business_id == business.id).order_by(BusinessBrief.created_at.desc())
    )
    score = session.scalar(
        select(OpportunityScore)
        .where(OpportunityScore.business_id == business.id)
        .order_by(OpportunityScore.created_at.desc())
    )
    demo = session.scalar(
        select(GeneratedDemo)
        .where(GeneratedDemo.business_id == business.id, GeneratedDemo.status == "approved")
        .order_by(GeneratedDemo.created_at.desc())
    )
    if business.state == LeadState.SUPPRESSED.value:
        return False, "suppressed", brief, score, demo
    if brief:
        risks = session.scalars(select(BusinessBriefRisk).where(BusinessBriefRisk.business_brief_id == brief.id)).all()
        if any(r.code in {"SUPPRESSED", "DO_NOT_CONTACT"} for r in risks):
            return False, "do_not_contact", brief, score, demo
        if any(r.code == "AMBIGUOUS_IDENTITY" for r in risks):
            return False, "ambiguous_identity", brief, score, demo
    if brief is None:
        return False, "brief_required", brief, score, demo
    if score is None:
        return False, "score_required", brief, score, demo
    interest = session.scalar(
        select(LeadCrmEvent).where(LeadCrmEvent.business_id == business.id, LeadCrmEvent.event_type == "reply_received")
    )
    if (
        business.state not in {LeadState.REPLIED.value, LeadState.MEETING.value, LeadState.PROPOSAL.value}
        and not interest
        and not operator_requested
        and not demo
    ):
        return False, "no_interest", brief, score, demo
    if not demo and not operator_requested:
        return False, "no_approved_demo", brief, score, demo
    return True, None, brief, score, demo


def choose_type(business: Business, brief: BusinessBrief, requested: str | None) -> str:
    if requested:
        return requested
    if brief.recommended_next_action == "generate_demo":
        return "starter_website_build"
    if brief.recommended_next_action == "conversion_upgrade_offer":
        return "conversion_upgrade"
    return "technical_cleanup"


def generate(
    session: Session, business: Business, requested_type: str | None = None, operator_requested: bool = False
) -> ProposalPackage:
    ok, reason, brief, score, demo = eligibility(session, business, operator_requested)
    if not ok or brief is None:
        raise ValueError(reason or "not_eligible")
    p = ProposalPackage(
        business_id=business.id,
        brief_id=brief.id,
        score_id=score.id if score else None,
        demo_id=demo.id if demo else None,
        version=VERSION,
        proposal_type=choose_type(business, brief, requested_type),
        status="draft",
        summary=f"Evidence-backed {business.display_name} proposal pack for operator review.",
    )
    session.add(p)
    session.flush()
    ev = _evidence(brief, score)
    sections = [
        (
            "business_context",
            "Business context",
            f"{business.display_name} is recorded as {business.category or 'a local business'} "
            f"in {business.locality or 'the recorded locality'}.",
        ),
        (
            "observed_opportunity",
            "Observed opportunity",
            "The opportunity summary is based on stored audit, brief, and score evidence; "
            "no performance outcome is promised.",
        ),
        (
            "recommended_solution",
            "Recommended solution",
            f"Prepare a {p.proposal_type.replace('_', ' ')} concept for operator and client discussion.",
        ),
        (
            "deliverables",
            "Proposed deliverables",
            "Scope to be confirmed with the client; this pack uses placeholders and does not constitute a contract.",
        ),
        ("assumptions", "Assumptions", "Business facts and requirements will be confirmed before any implementation."),
        (
            "exclusions",
            "Exclusions",
            "No hosting, payments, legal advice, contract, domain purchase, or automated outreach is included.",
        ),
        (
            "client_questions",
            "Client questions",
            "Confirm goals, services, assets, preferred calls to action, timeline, and budget.",
        ),
        ("timeline", "Timeline", "Timeline placeholder — confirm after scope and dependencies are agreed."),
        ("pricing_placeholder", "Pricing", "Pricing placeholder — operator must replace with an approved quote."),
        (
            "next_step",
            "Next step",
            "Operator review, then discuss the evidence-backed scope with the business if appropriate.",
        ),
    ]
    for i, (kind, heading, body) in enumerate(sections):
        session.add(
            ProposalSection(proposal_id=p.id, section_type=kind, heading=heading, body=body, sort_order=i, evidence=ev)
        )
    session.add(
        ProposalLineItem(
            proposal_id=p.id,
            code="scope_placeholder",
            label="Scope placeholder",
            description="Replace with approved scope after operator/client review.",
            unit="placeholder",
            pricing_status="placeholder",
        )
    )
    session.add(
        ProposalAssumption(
            proposal_id=p.id,
            code="facts_to_confirm",
            text="Verify all business facts and requested outcomes before quoting.",
            category="evidence",
        )
    )
    session.commit()
    session.refresh(p)
    return p


def export_package(session: Session, p: ProposalPackage, settings: Settings) -> ProposalExport:
    root = Path(settings.export_root).resolve() / "proposals" / str(p.id)
    root.mkdir(parents=True, exist_ok=True)
    sections = session.scalars(
        select(ProposalSection).where(ProposalSection.proposal_id == p.id).order_by(ProposalSection.sort_order)
    ).all()
    items = session.scalars(select(ProposalLineItem).where(ProposalLineItem.proposal_id == p.id)).all()
    md = "# Proposal pack\n\n" + "\n\n".join(f"## {s.heading}\n{s.body}" for s in sections)
    (root / "proposal.md").write_text(md, encoding="utf-8")
    (root / "proposal-summary.json").write_text(
        json.dumps(
            {
                "proposal_id": str(p.id),
                "business_id": str(p.business_id),
                "proposal_type": p.proposal_type,
                "status": p.status,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "proposal-sections.json").write_text(
        json.dumps([{"type": s.section_type, "heading": s.heading, "body": s.body} for s in sections], indent=2),
        encoding="utf-8",
    )
    with (root / "proposal-line-items.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "label", "description", "pricing_status"])
        w.writerows((i.code, i.label, i.description, i.pricing_status) for i in items)
    (root / "proposal-evidence.json").write_text(json.dumps([s.evidence for s in sections], indent=2), encoding="utf-8")
    files = {
        n: str(root / n)
        for n in [
            "proposal.md",
            "proposal-summary.json",
            "proposal-sections.json",
            "proposal-line-items.csv",
            "proposal-evidence.json",
        ]
    }
    ex = ProposalExport(proposal_id=p.id, status="exported", files=files)
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex
