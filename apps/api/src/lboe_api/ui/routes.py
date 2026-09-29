# ruff: noqa: E501
from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from lboe_api.db import (
    AuditArtifact,
    AuditRun,
    Business,
    BusinessBrief,
    Campaign,
    Contact,
    DeliveryChecklistItem,
    DeliveryMilestone,
    DeliveryProject,
    DemoArtifact,
    DemoPreviewAccessEvent,
    DemoPreviewLink,
    DemoQaRun,
    EnrichmentRun,
    GeneratedDemo,
    LeadCrmEvent,
    ManualFollowUpTask,
    Operator,
    OperatorAssignment,
    OperatorAuditEvent,
    OperatorComment,
    OperatorSession,
    OpportunityComponent,
    OpportunityHold,
    OpportunityScore,
    OutreachDraftMessage,
    OutreachDraftPackage,
    OutreachObjection,
    PilotExportRun,
    PilotRetrospective,
    PilotRun,
    PilotSourcePolicyAcknowledgement,
    ProposalPackage,
    SourceObservation,
    SuppressionEntry,
    Website,
)
from lboe_api.demo_generator import qa_explanations
from lboe_api.main import SessionLocal, settings
from lboe_api.pilot_service import (
    POLICY_VERSION,
    audit,
    cap_available,
    counters,
    generate_export,
    pilot_for_business,
    readiness_summary,
)
from lboe_api.reporting_service import build_pilot_report

router = APIRouter()
DISCLAIMER = "Concept preview prepared independently for demonstration. Not the official website of this business."


def session() -> Session:
    return SessionLocal()


@router.get("/ui/login", response_class=HTMLResponse)
def login_page() -> HTMLResponse:
    return page(
        "Operator login",
        "<form method='post'><label>Operator token <input name='token' type='password' required></label><button>Login</button></form><p>Internal operator access only. Configure LBOE_AUTH_ENABLED and LBOE_OPERATOR_AUTH_TOKEN.</p>",
    )


@router.post("/ui/login")
def login(token: str = Form(...), db: Session = Depends(session)) -> Response:
    if not settings.operator_auth_token or not secrets.compare_digest(token, settings.operator_auth_token):
        raise HTTPException(status_code=401, detail="invalid_operator_token")
    operator = db.scalar(select(Operator).where(Operator.active.is_(True)).order_by(Operator.created_at))
    if operator is None:
        raise HTTPException(status_code=409, detail="active_operator_required")
    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    session_hash = hmac.new(settings.auth_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    csrf_hash = hashlib.sha256(csrf.encode()).hexdigest()
    from datetime import timedelta

    db.add(
        OperatorSession(
            operator_id=operator.id,
            session_hash=session_hash,
            csrf_hash=csrf_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
    )
    db.commit()
    response = RedirectResponse("/ui", status_code=303)
    response.set_cookie(
        "lboe_session", raw, httponly=True, secure=settings.secure_cookies, samesite="lax", max_age=28800
    )
    response.set_cookie(
        "lboe_csrf", csrf, httponly=False, secure=settings.secure_cookies, samesite="lax", max_age=28800
    )
    return response


@router.post("/ui/logout")
def logout(request: Request, db: Session = Depends(session)) -> Response:
    token = request.cookies.get("lboe_session")
    if token:
        session_hash = hmac.new(settings.auth_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        row = db.scalar(select(OperatorSession).where(OperatorSession.session_hash == session_hash))
        if row:
            row.revoked_at = datetime.now(UTC)
            db.commit()
    response = RedirectResponse("/ui/login", status_code=303)
    response.delete_cookie("lboe_session")
    response.delete_cookie("lboe_csrf")
    return response


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)} · LBOE</title><link rel='stylesheet' href='/ui/static/ui.css'></head><body><header><a href='/ui'><strong>LBOE Operator Cockpit</strong></a><nav><a href='/ui'>Dashboard</a><a href='/ui/opportunities'>Opportunities</a><a href='/ui/campaigns'>Campaigns</a><a href='/ui/queues'>Queues</a><a href='/ui/queues/proposal-ready'>Proposals</a><a href='/ui/queues/delivery'>Delivery</a><a href='/ui/pilots'>Pilots</a><a href='/ui/reports/pilot'>Reports</a><a href='/ui/operators'>Admin</a><a href='/ui/system'>System</a></nav></header><div class='safety'>System delivery is disabled. LBOE does not send email, WhatsApp, SMS, review requests, or CRM messages.</div><main><p class='muted'><a href='/ui'>Dashboard</a> / {esc(title)}</p><h1>{esc(title)}</h1>{body}</main></body></html>"""
    )


def metric_cards(report: dict[str, Any]) -> str:
    counts = {item["stage"]: item["count"] for item in report["funnel_metrics"]}
    keys = (
        "DISCOVERED",
        "SCORED",
        "REVIEW_PENDING",
        "APPROVED_FOR_OUTREACH",
        "OUTREACH_READY",
        "CONTACTED",
        "REPLIED",
        "MEETING",
        "PROPOSAL",
        "WON",
        "LOST",
    )
    return (
        "<div class='cards'>"
        + "".join(
            f"<div class='card'><span>{key.replace('_', ' ')}</span><b>{counts.get(key, 0)}</b></div>" for key in keys
        )
        + "</div>"
    )


def _review_metrics(db: Session, business_id: uuid.UUID) -> dict[str, float | int | None]:
    """Read optional rating/review-count facts without changing the canonical model."""

    observations = db.scalars(
        select(SourceObservation)
        .where(SourceObservation.business_id == business_id)
        .order_by(SourceObservation.observed_at.desc())
    ).all()
    rating: float | None = None
    review_count: int | None = None
    for observation in observations:
        field = observation.field.casefold().replace("-", "_")
        raw = observation.value
        if raw is None:
            continue
        if rating is None and (field in {"rating", "review_rating", "reviews_rating"} or field.endswith(".rating")):
            try:
                candidate = float(str(raw).replace(",", ".").strip())
            except ValueError:
                candidate = -1
            if 0 <= candidate <= 5:
                rating = candidate
        if review_count is None and (
            field in {"review_count", "reviews", "reviews_count", "rating_count"} or field.endswith(".review_count")
        ):
            try:
                candidate_count = int(float(str(raw).replace(",", "").strip()))
            except ValueError:
                candidate_count = -1
            if candidate_count >= 0:
                review_count = candidate_count
        if rating is not None and review_count is not None:
            break
    return {"rating": rating, "review_count": review_count}


def build_opportunity_cards(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    """Build a small, explainable queue of the next best operator actions.

    This is deliberately a UI projection over existing records. It does not
    change scoring, lifecycle state, or outreach eligibility.
    """

    technical_codes = {
        "MISSING_H1",
        "MISSING_TITLE",
        "MISSING_META_DESCRIPTION",
        "MISSING_VIEWPORT_META",
        "LOW_IMAGE_ALT_COVERAGE",
        "CONSOLE_ERRORS",
        "FAILED_FIRST_PARTY_REQUESTS",
    }
    conversion_codes = {"NO_BOOKING_PATH", "NO_WHATSAPP_CTA", "NO_CLICK_TO_CALL", "NO_CONTACT_FORM"}
    component_labels = {
        "NO_WEBSITE": "No website found",
        "NO_BOOKING_PATH": "No booking path detected",
        "NO_WHATSAPP_CTA": "No WhatsApp action detected",
        "NO_CLICK_TO_CALL": "No click-to-call path detected",
        "NO_CONTACT_FORM": "No contact form detected",
        "MISSING_H1": "Primary page heading is missing",
        "MISSING_TITLE": "Page title is missing",
        "MISSING_META_DESCRIPTION": "Meta description is missing",
        "MISSING_VIEWPORT_META": "Mobile viewport setting is missing",
        "LOW_IMAGE_ALT_COVERAGE": "Some images lack alternative text",
        "CONSOLE_ERRORS": "Browser console errors were observed",
        "FAILED_FIRST_PARTY_REQUESTS": "First-party requests failed",
    }

    cards: list[dict[str, Any]] = []
    businesses = db.scalars(select(Business).order_by(Business.updated_at.desc(), Business.display_name)).all()
    review_metrics = {business.id: _review_metrics(db, business.id) for business in businesses}
    for business in businesses:
        own_review = review_metrics[business.id]
        peers = [
            (peer, review_metrics[peer.id])
            for peer in businesses
            if peer.id != business.id
            and peer.campaign_id == business.campaign_id
            and (not business.category or not peer.category or peer.category.casefold() == business.category.casefold())
            and (not business.locality or not peer.locality or peer.locality.casefold() == business.locality.casefold())
            and (review_metrics[peer.id]["rating"] is not None or review_metrics[peer.id]["review_count"] is not None)
        ]
        review_evidence: list[str] = []
        own_rating = own_review["rating"]
        own_count = own_review["review_count"]
        if isinstance(own_rating, float) and own_rating < 4.0:
            review_evidence.append(f"Rating: {own_rating:.1f}")
        if isinstance(own_count, int) and own_count < 25:
            review_evidence.append(f"Reviews: {own_count}")
        peer_rating = max(
            (peer_metrics["rating"] for _peer, peer_metrics in peers if isinstance(peer_metrics["rating"], float)),
            default=None,
        )
        if isinstance(own_rating, float) and isinstance(peer_rating, float) and peer_rating - own_rating >= 0.4:
            peer = next(peer for peer, metrics in peers if metrics["rating"] == peer_rating)
            review_evidence.append(
                f"Peer comparison: {peer.display_name} shows {peer_rating:.1f} stars vs {own_rating:.1f}"
            )
        peer_count = max(
            (
                peer_metrics["review_count"]
                for _peer, peer_metrics in peers
                if isinstance(peer_metrics["review_count"], int)
            ),
            default=None,
        )
        if (
            isinstance(own_count, int)
            and isinstance(peer_count, int)
            and peer_count >= own_count * 2
            and peer_count >= own_count + 20
        ):
            peer = next(peer for peer, metrics in peers if metrics["review_count"] == peer_count)
            review_evidence.append(f"Peer comparison: {peer.display_name} shows {peer_count} reviews vs {own_count}")
        review_gap = bool(review_evidence) and (
            (isinstance(own_rating, float) and own_rating < 4.0)
            or (isinstance(own_count, int) and own_count < 25)
            or any("Peer comparison" in item for item in review_evidence)
        )
        score = db.scalar(
            select(OpportunityScore)
            .where(OpportunityScore.business_id == business.id)
            .order_by(OpportunityScore.created_at.desc())
        )
        brief = db.scalar(
            select(BusinessBrief)
            .where(BusinessBrief.business_id == business.id)
            .order_by(BusinessBrief.created_at.desc())
        )
        website = db.scalar(
            select(Website).where(Website.business_id == business.id).order_by(Website.checked_at.desc())
        )
        demo = db.scalar(
            select(GeneratedDemo)
            .where(GeneratedDemo.business_id == business.id)
            .order_by(GeneratedDemo.created_at.desc())
        )
        proposal = db.scalar(
            select(ProposalPackage)
            .where(ProposalPackage.business_id == business.id)
            .order_by(ProposalPackage.created_at.desc())
        )
        delivery = db.scalar(
            select(DeliveryProject)
            .where(DeliveryProject.business_id == business.id)
            .order_by(DeliveryProject.updated_at.desc())
        )
        suppression = db.scalar(
            select(SuppressionEntry)
            .where(SuppressionEntry.business_id == business.id)
            .order_by(SuppressionEntry.created_at.desc())
        )
        components = (
            db.scalars(
                select(OpportunityComponent)
                .where(OpportunityComponent.opportunity_score_id == score.id)
                .order_by(OpportunityComponent.points.desc())
            ).all()
            if score
            else []
        )
        holds = (
            db.scalars(select(OpportunityHold).where(OpportunityHold.opportunity_score_id == score.id)).all()
            if score
            else []
        )
        reasons: list[str] = []
        if review_gap:
            reasons.extend(review_evidence)
        if website is None and len(reasons) < 4:
            reasons.append("No website found")
        for component in components:
            label = component_labels.get(component.code)
            if label and label not in reasons:
                reasons.append(label)
            if len(reasons) >= 4:
                break
        if not reasons and website is not None:
            reasons.append("Website presence recorded")
        if business.normalized_phone and len(reasons) < 4:
            reasons.append("Phone contact available")
        if score and len(reasons) < 4:
            reasons.append(f"Opportunity score: {score.score} ({score.band})")

        blockers = [entry.reason for entry in ([suppression] if suppression else [])]
        blockers.extend(hold.reason for hold in holds)
        blocked = bool(blockers) or business.state in {"SUPPRESSED", "ARCHIVED"}
        if business.state == "SUPPRESSED" and not blockers:
            blockers.append("Business is suppressed")
        if any(hold.code == "AMBIGUOUS_IDENTITY" for hold in holds):
            blocked = True

        if blocked:
            offer = "No action"
            next_label = "View details"
            next_url = f"/ui/businesses/{business.id}"
        elif delivery:
            offer = "Delivery Follow-up"
            next_label = "Continue delivery"
            next_url = f"/ui/delivery-projects/{delivery.id}"
        elif proposal:
            offer = "Proposal Follow-up"
            next_label = "Review proposal"
            next_url = f"/ui/proposals/{proposal.id}"
        elif demo and demo.status in {"qa_passed", "review_pending", "approved"}:
            offer = "Starter Website" if demo.demo_type == "starter_website" else "Conversion Upgrade"
            next_label = "Review concept"
            next_url = f"/ui/demos/{demo.id}/preview"
        elif review_gap:
            offer = "Review Gap Opportunity"
            next_label = "Review evidence"
            next_url = f"/ui/businesses/{business.id}"
        elif website is None:
            offer = "Starter Website"
            next_label = "View opportunity"
            next_url = f"/ui/businesses/{business.id}"
        elif any(component.code in conversion_codes for component in components):
            offer = "Conversion Upgrade"
            next_label = "Review evidence"
            next_url = f"/ui/businesses/{business.id}"
        elif any(component.code in technical_codes for component in components):
            offer = "Technical Cleanup"
            next_label = "Review evidence"
            next_url = f"/ui/businesses/{business.id}"
        elif score and score.recommended_next_action == "score_only":
            offer = "Score Only"
            next_label = "Review details"
            next_url = f"/ui/businesses/{business.id}"
        else:
            offer = "Review Required"
            next_label = "Review evidence"
            next_url = f"/ui/businesses/{business.id}"

        confidence = "Needs review"
        confidence_value = brief.confidence if brief else (0.85 if score and score.band == "high" else 0.6)
        if not blocked and confidence_value >= 0.85:
            confidence = "High confidence"
        elif not blocked and confidence_value >= 0.65:
            confidence = "Medium confidence"
        score_value = score.score if score else None
        priority = (0 if blocked else 100) + (score_value or 0)
        if demo and demo.status in {"qa_passed", "review_pending", "approved"}:
            priority += 25
        if proposal:
            priority += 35
        if delivery:
            priority += 45
        cards.append(
            {
                "id": str(business.id),
                "business_id": str(business.id),
                "business_name": business.display_name,
                "locality": business.locality or business.address_text or "Location not verified",
                "state": business.state,
                "score": score_value,
                "confidence_label": confidence,
                "recommended_offer": offer,
                "reasons": reasons[:4],
                "competitor_evidence": review_evidence[:3],
                "review_gap": review_gap,
                "review_rating": own_rating,
                "review_count": own_count,
                "blockers": blockers[:3],
                "blocked": blocked,
                "next_action_label": next_label,
                "next_action_url": next_url,
                "detail_url": f"/ui/businesses/{business.id}",
                "priority": priority,
            }
        )
    cards.sort(key=lambda item: (-item["priority"], item["business_name"].lower()))
    return cards[:limit]


def opportunity_cards_html(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "<div class='empty-state'>No opportunity cards yet. Discover or import businesses to begin.</div>"
    rendered = []
    for card in cards:
        score = f"Score {card['score']}" if card["score"] is not None else "Not scored"
        reasons = "".join(f"<li>✓ {esc(reason)}</li>" for reason in card["reasons"])
        competitor_evidence = (
            "<div class='competitor-evidence'><strong>Peer comparison</strong><ul>"
            + "".join(f"<li>{esc(item)}</li>" for item in card.get("competitor_evidence", []))
            + "</ul></div>"
            if card.get("competitor_evidence")
            else ""
        )
        blockers = (
            f"<div class='opportunity-blocker'><strong>Blocked:</strong> {esc('; '.join(card['blockers']))}</div>"
            if card["blockers"]
            else ""
        )
        action = (
            f"<a class='button button-primary button-small' href='{esc(card['next_action_url'])}'>{esc(card['next_action_label'])}</a>"
            if not card["blocked"] or card["next_action_label"] == "View details"
            else ""
        )
        rendered.append(
            f"<article class='opportunity-card'><div class='opportunity-card-top'><span class='badge'>{esc(card['confidence_label'])}</span><span class='opportunity-score'>{esc(score)}</span></div><h2><a href='{esc(card['detail_url'])}'>{esc(card['business_name'])}</a></h2><p class='muted'>{esc(card['locality'])} · {esc(card['state'].replace('_', ' ').title())}</p><div class='opportunity-offer'><span>Recommended offer</span><strong>{esc(card['recommended_offer'])}</strong></div><h3>Why this matters</h3><ul class='opportunity-reasons'>{reasons or '<li>Evidence is still being collected</li>'}</ul>{competitor_evidence}{blockers}<div class='opportunity-actions'>{action}<a class='button button-secondary button-small' href='{esc(card['detail_url'])}'>View details</a></div></article>"
        )
    return "<div class='opportunity-grid'>" + "".join(rendered) + "</div>"


def map_panel(campaign: Any, businesses: Sequence[Business]) -> str:
    """Render a real Google Maps view with a safe local lead fallback."""
    geography = esc(getattr(campaign, "geography", None) or "Campaign area")
    query = (getattr(campaign, "geography", None) or "") + " " + (getattr(campaign, "vertical", None) or "")
    maps_query = __import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(query)
    maps_url = "https://www.google.com/maps/search/?api=1&query=" + __import__(
        "urllib.parse", fromlist=["quote_plus"]
    ).quote_plus(query)
    lead_links = (
        "".join(
            f"<a class='map-lead' href='/ui/businesses/{business.id}'><span class='map-dot'></span><span>{esc(business.display_name)}</span><small>{esc(business.state)}</small></a>"
            for business in businesses[:8]
        )
        or "<p class='muted'>Run discovery to add businesses to this campaign.</p>"
    )
    return (
        f"<div class='map-caption' style='display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 8px;padding:0 2px'><strong>Geographic view</strong><span class='muted'>Campaign area · {geography}</span></div><div class='map-shell'><iframe class='map-iframe' src='https://www.google.com/maps?q={maps_query}&output=embed' loading='lazy' referrerpolicy='no-referrer-when-downgrade' title='Google Maps view of {geography}'></iframe>"
        f"<div class='map-overlay'><div class='map-context' style='position:absolute;left:50%;top:50%;z-index:2;display:grid;gap:4px;transform:translate(-50%,-50%);padding:15px 18px;border-radius:12px;background:rgba(20,33,61,.86);color:#fff;text-align:center;max-width:270px'><strong>Map view</strong><span style='font-size:.75rem;color:#dce4f2'>Open the full map for live Google Maps pins.</span></div><a class='button button-secondary map-open' href='{maps_url}' target='_blank' rel='noreferrer'>Open full map</a></div></div>"
        f"<div class='map-leads'><div class='section-head'><div><h3>Leads in this area</h3><p class='muted'>Select a lead to see evidence and the next action.</p></div><span class='badge'>{len(businesses)} businesses</span></div><div class='map-lead-list'>{lead_links}</div></div>"
    )


def next_action_panel(report: dict[str, Any]) -> str:
    counts = {item["stage"]: item["count"] for item in report["funnel_metrics"]}
    if counts.get("REVIEW_PENDING", 0):
        title, copy, href, label = (
            "Review demos",
            "Approved concepts are waiting for a human decision.",
            "/ui/queues",
            "Open review queue",
        )
    elif counts.get("OUTREACH_READY", 0):
        title, copy, href, label = (
            "Ready for manual outreach",
            "A lead has passed the readiness gate. Review the approved channel before recording contact.",
            "/ui/queues",
            "Open readiness queue",
        )
    elif counts.get("CONTACTED", 0):
        title, copy, href, label = (
            "Log the next response",
            "Keep the funnel current with a reply, meeting, or no-response note.",
            "/ui/queues",
            "Open CRM queue",
        )
    elif counts.get("DISCOVERED", 0):
        title, copy, href, label = (
            "Start with your discovered leads",
            "Open a campaign, inspect the map, then work the highest-signal lead first.",
            "/ui/campaigns",
            "Open campaigns",
        )
    else:
        title, copy, href, label = (
            "Create your first campaign",
            "Choose a geography and vertical to begin the operator workflow.",
            "/ui/campaigns",
            "Create campaign",
        )
    return f"<section class='next-action'><div><span class='eyebrow'>Recommended next step</span><h2>{title}</h2><p>{copy}</p></div><a class='button button-primary' href='{href}'>{label}</a></section>"


@router.get("/ui", response_class=HTMLResponse)
def dashboard(db: Session = Depends(session)) -> HTMLResponse:
    report = build_pilot_report(db)
    quality = {item["code"]: item["count"] for item in report["quality_metrics"]}
    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    campaign = max(
        campaigns,
        key=lambda item: (
            len(db.scalars(select(Business).where(Business.campaign_id == item.id)).all()),
            item.created_at,
        ),
        default=None,
    )
    campaign_businesses = (
        db.scalars(select(Business).where(Business.campaign_id == campaign.id).order_by(Business.display_name)).all()
        if campaign
        else []
    )
    opportunity_cards = build_opportunity_cards(db, limit=5)
    body = (
        "<div class='hero'><div class='hero-copy'><div class='eyebrow'>Field operations console</div><h1>Turn a map of businesses into your next best action.</h1><p>Start with a campaign, inspect the map, and work each lead through evidence, score, demo, proposal, and delivery.</p></div><div class='hero-actions'><a class='button button-primary' href='/ui/opportunities'>Open Opportunity Cards</a><a class='button button-secondary' href='/ui/campaigns'>Open campaigns</a><a class='button button-secondary' href='/ui/queues'>View queues</a></div></div>"
        + metric_cards(report)
        + next_action_panel(report)
        + "<section class='section'><div class='section-head'><div><div class='eyebrow'>Revenue focus</div><h2>Opportunity Cards</h2><p class='muted'>The clearest next actions from your current evidence.</p></div><a class='button button-secondary button-small' href='/ui/opportunities'>View all</a></div>"
        + opportunity_cards_html(opportunity_cards)
        + "</section>"
        + f"<div class='layout-grid'><section class='section'><div class='section-head'><div><div class='eyebrow'>Geographic view</div><h2>{esc(campaign.name) if campaign else 'Your campaign map'}</h2></div><a class='button button-secondary' href='/ui/campaigns'>Manage campaigns</a></div>{map_panel(campaign, campaign_businesses) if campaign else map_panel(type('CampaignView', (), {'geography': 'Choose a geography', 'vertical': 'local business'})(), [])}</section><section class='section'><div class='eyebrow'>Today</div><h2>What needs attention</h2><div class='stat-line'><span>System delivery</span><strong>{quality.get('system_delivery_count', 0)}</strong></div><div class='stat-line'><span>Failed / blocked jobs</span><strong>{quality.get('jobs_failed', quality.get('jobs_failed_or_not_eligible', 0))}</strong></div><div class='stat-line'><span>Approved demos</span><strong>{quality.get('approved_demos', 0)}</strong></div><div class='stat-line'><span>Proposal-ready</span><strong>{quality.get('proposal_ready_queue_count', 0)}</strong></div><p class='muted'>Every action is operator-controlled. LBOE never sends messages.</p></section></div>"
    )
    return page("Pilot dashboard", body)


@router.get("/ui/opportunities", response_class=HTMLResponse)
def opportunities(db: Session = Depends(session)) -> HTMLResponse:
    cards = build_opportunity_cards(db, limit=50)
    body = (
        "<div class='page-intro'><div><span class='eyebrow'>Revenue focus</span><h1>Opportunity Cards</h1><p class='muted'>Find the next best operator action in under five seconds. Each card combines the business, the reason it matters, the best-fit offer, confidence, and a safe next step.</p></div><span class='badge'>Operator-controlled</span></div>"
        "<div class='notice'><strong>How to use this page:</strong> start with the highest-signal card, open the recommended safe action, and verify the evidence before preparing a proposal or delivery step.</div>"
        "<p class='muted opportunity-safety'>Review Gap Opportunities identify businesses whose review profile may look weaker than comparable local or campaign peers. LBOE does not send email, WhatsApp, SMS, review requests, or CRM messages. All outreach and review work happens manually outside LBOE.<br>Proposal packs are not contracts. Delivery approvals are operator assertions, not e-signatures.</p>"
        + opportunity_cards_html(cards)
    )
    return page("Opportunity Cards", body)


@router.get("/ui/campaigns", response_class=HTMLResponse)
def campaigns(db: Session = Depends(session)) -> HTMLResponse:
    rows = []
    seen: set[tuple[str, str, str | None]] = set()
    for campaign in db.scalars(
        select(__import__("lboe_api.db", fromlist=["Campaign"]).Campaign).order_by(
            __import__("lboe_api.db", fromlist=["Campaign"]).Campaign.created_at.desc()
        )
    ).all():
        key = (campaign.name, campaign.vertical, campaign.geography)
        if key in seen:
            continue
        seen.add(key)
        count = (
            db.scalar(select(Business).where(Business.campaign_id == campaign.id).count())
            if False
            else len(db.scalars(select(Business).where(Business.campaign_id == campaign.id)).all())
        )
        rows.append(
            f"<tr><td><a class='table-primary' href='/ui/campaigns/{campaign.id}'>{esc(campaign.name)}</a><small class='table-sub'>Latest run · {esc(campaign.created_at)}</small></td><td>{esc(campaign.vertical)}</td><td>{esc(campaign.geography)}</td><td><strong>{count}</strong></td><td><a class='button button-small button-secondary' href='/ui/campaigns/{campaign.id}'>Open workspace</a></td></tr>"
        )
    table = (
        "<table><tr><th>Campaign</th><th>Vertical</th><th>Geography</th><th>Leads</th><th></th></tr>"
        + "".join(rows)
        + "</table>"
    )
    form = "<section class='section create-panel'><div><span class='eyebrow'>New workspace</span><h2>Start a campaign</h2><p class='muted'>Choose the market you want to work. You can add discovery results after the campaign is created.</p></div><form method='post' action='/ui/campaigns'><input name='name' placeholder='Campaign name' required><input name='vertical' placeholder='Vertical' required><input name='geography' placeholder='Geography'><button class='button-primary'>Create campaign</button></form></section>"
    return page(
        "Campaigns",
        "<div class='page-intro'><div><span class='eyebrow'>Workspaces</span><h1>Campaigns</h1><p class='muted'>One workspace per market. Open a campaign to see its map and lead queue.</p></div></div>"
        + table
        + form,
    )


@router.post("/ui/campaigns")
def create_campaign(
    name: str = Form(...), vertical: str = Form(...), geography: str = Form(""), db: Session = Depends(session)
) -> RedirectResponse:
    from lboe_api.db import Campaign

    campaign = Campaign(name=name, vertical=vertical, geography=geography or None)
    db.add(campaign)
    db.commit()
    return RedirectResponse(f"/ui/campaigns/{campaign.id}", status_code=303)


@router.post("/ui/campaigns/{campaign_id}/discover")
async def discover_from_ui(
    campaign_id: uuid.UUID,
    queries: str = Form(...),
    geography: str = Form(""),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    max_results: int = Form(25),
    db: Session = Depends(session),
) -> RedirectResponse:
    """Run the provider-neutral discovery workflow from the operator console."""
    from lboe_api.main import DiscoveryRequestBody, discover_campaign

    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "campaign_not_found")
    query_list = [item.strip() for item in queries.split(",") if item.strip()]
    if not query_list:
        raise HTTPException(422, "at_least_one_query_required")
    body = DiscoveryRequestBody(
        queries=query_list,
        geography=geography.strip() or campaign.geography,
        latitude=latitude,
        longitude=longitude,
        max_results=max_results,
        timeout_seconds=300,
        idempotency_key=f"ui:{campaign_id}:{','.join(query_list)}:{latitude}:{longitude}",
    )
    try:
        result = await discover_campaign(campaign_id, body, db)
        status = result.get("status", "completed")
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            status = f"error: {detail.get('error', 'discovery_failed')} (job {detail.get('job_id', 'unknown')})"
        else:
            status = f"error: {detail}"
    except Exception as exc:  # noqa: BLE001
        status = f"error: {type(exc).__name__}"
    encoded_status = __import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(status)
    return RedirectResponse(f"/ui/campaigns/{campaign_id}?discovery_status={encoded_status}", status_code=303)


@router.get("/ui/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(
    campaign_id: uuid.UUID,
    state: str | None = None,
    action: str | None = None,
    band: str | None = None,
    website_status: str | None = None,
    q: str | None = None,
    discovery_status: str | None = None,
    db: Session = Depends(session),
) -> HTMLResponse:
    from lboe_api.db import Campaign

    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "campaign_not_found")
    businesses = db.scalars(
        select(Business).where(Business.campaign_id == campaign_id).order_by(Business.display_name)
    ).all()
    rows = []
    visible_businesses: list[Business] = []
    for business in businesses:
        score = db.scalar(
            select(OpportunityScore)
            .where(OpportunityScore.business_id == business.id)
            .order_by(OpportunityScore.created_at.desc())
        )
        brief = db.scalar(
            select(BusinessBrief)
            .where(BusinessBrief.business_id == business.id)
            .order_by(BusinessBrief.created_at.desc())
        )
        website = db.scalar(select(Contact).where(Contact.business_id == business.id, Contact.channel == "website"))
        if (
            state
            and business.state != state
            or q
            and q.lower() not in business.display_name.lower()
            or action
            and (not brief or brief.recommended_next_action != action)
            or band
            and (not score or score.band != band)
            or website_status == "no_website"
            and website is not None
            or website_status == "website_present"
            and website is None
        ):
            continue
        visible_businesses.append(business)
        demo = db.scalar(
            select(GeneratedDemo)
            .where(GeneratedDemo.business_id == business.id)
            .order_by(GeneratedDemo.created_at.desc())
        )
        website_label = "No website" if website is None else "Website present"
        rows.append(
            f"<tr><td><a class='table-primary' href='/ui/businesses/{business.id}'>{esc(business.display_name)}</a><small class='table-sub'>{esc(website_label)}</small></td><td>{esc(business.category)}</td><td>{esc(business.locality)}</td><td><span class='badge'>{esc(business.state)}</span></td><td>{score.score if score else '—'}</td><td>{esc(score.band if score else '')}</td><td>{esc(brief.recommended_next_action if brief else '')}</td><td>{esc(demo.status if demo else '')}</td></tr>"
        )
    filters = f"<form class='lead-filters' method='get'><input name='q' value='{esc(q)}' placeholder='Search business'><select name='website_status'><option value=''>All website statuses</option><option value='no_website' {'selected' if website_status == 'no_website' else ''}>No website</option><option value='website_present' {'selected' if website_status == 'website_present' else ''}>Website present</option></select><input name='state' value='{esc(state)}' placeholder='State'><input name='action' value='{esc(action)}' placeholder='Recommended action'><input name='band' value='{esc(band)}' placeholder='Score band'><button>Filter leads</button></form>"
    table = (
        "<table><tr><th>Business</th><th>Category</th><th>Locality</th><th>State</th><th>Score</th><th>Band</th><th>Action</th><th>Demo</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    intro = f"<div class='hero'><div class='hero-copy'><div class='eyebrow'>Campaign workspace</div><h1>{esc(campaign.name)}</h1><p>{esc(campaign.vertical)} in {esc(campaign.geography or 'your target geography')}. Select a marker or a lead below to continue.</p></div><div class='hero-actions'><a class='button button-primary' href='/ui/queues'>Work the queues</a><a class='button button-secondary' href='https://www.google.com/maps/search/?api=1&query={__import__('urllib.parse', fromlist=['quote_plus']).quote_plus((campaign.geography or '') + ' ' + campaign.vertical)}' target='_blank' rel='noreferrer'>Open Google Maps</a></div></div>"
    discovery_notice = (
        f"<div class='notice'>Discovery result: <strong>{esc(discovery_status)}</strong>. Review the lead list below, then filter by website status.</div>"
        if discovery_status
        else ""
    )
    discovery_form = (
        "<section class='section discovery-panel'><div><span class='eyebrow'>Find businesses</span><h2>Run discovery in this campaign</h2><p class='muted'>Search Google Maps for a vertical and location. Coordinates are required by the maps provider and keep the search predictable.</p></div>"
        "<form method='post' action='/ui/campaigns/"
        + str(campaign_id)
        + "/discover'><input name='queries' placeholder='Queries, e.g. hair salons' required><input name='geography' value='"
        + esc(campaign.geography or "")
        + "' placeholder='Geography'><div class='discovery-coordinates'><input name='latitude' type='number' step='any' placeholder='Latitude' required><input name='longitude' type='number' step='any' placeholder='Longitude' required><input name='max_results' type='number' min='1' max='100' value='25' aria-label='Maximum results'></div><button class='button-primary'>Find businesses</button></form></section>"
    )
    return page(
        f"Campaign · {campaign.name}",
        discovery_notice
        + intro
        + discovery_form
        + map_panel(campaign, visible_businesses)
        + f"<section class='section'><div class='section-head'><h2>Lead list</h2><span class='badge'>{len(rows)} shown</span></div>{filters}{table}</section>",
    )


@router.get("/ui/businesses/{business_id}", response_class=HTMLResponse)
def business_detail(
    business_id: uuid.UUID,
    action_completed: str | None = None,
    action_error: str | None = None,
    db: Session = Depends(session),
) -> HTMLResponse:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(404, "business_not_found")
    score = db.scalar(
        select(OpportunityScore)
        .where(OpportunityScore.business_id == business_id)
        .order_by(OpportunityScore.created_at.desc())
    )
    brief = db.scalar(
        select(BusinessBrief).where(BusinessBrief.business_id == business_id).order_by(BusinessBrief.created_at.desc())
    )
    demos = db.scalars(
        select(GeneratedDemo).where(GeneratedDemo.business_id == business_id).order_by(GeneratedDemo.created_at.desc())
    ).all()
    proposals = db.scalars(
        select(ProposalPackage)
        .where(ProposalPackage.business_id == business_id)
        .order_by(ProposalPackage.created_at.desc())
    ).all()
    package = db.scalar(
        select(OutreachDraftPackage)
        .where(OutreachDraftPackage.business_id == business_id)
        .order_by(OutreachDraftPackage.created_at.desc())
    )
    enrichment_runs = db.scalars(
        select(EnrichmentRun).where(EnrichmentRun.business_id == business_id).order_by(EnrichmentRun.started_at.desc())
    ).all()
    events = db.scalars(
        select(LeadCrmEvent).where(LeadCrmEvent.business_id == business_id).order_by(LeadCrmEvent.occurred_at.desc())
    ).all()
    comments = db.scalars(
        select(OperatorComment)
        .where(OperatorComment.business_id == business_id)
        .order_by(OperatorComment.created_at.desc())
    ).all()
    assignments = db.scalars(
        select(OperatorAssignment)
        .where(OperatorAssignment.business_id == business_id)
        .order_by(OperatorAssignment.created_at.desc())
    ).all()
    demo_html = (
        "".join(
            f"<li><a href='/ui/demos/{demo.id}/preview'>Demo {demo.id}</a> — {esc(demo.status)} {('<strong>QA failed: inspect checks; regenerate or mark manual edit. Sharing blocked.</strong>' if demo.status == 'qa_failed' else '')} <a href='/ui/demos/{demo.id}/preview-links'>preview links</a></li>"
            for demo in demos
        )
        or "<li>None</li>"
    )
    proposal_html = (
        "".join(
            f"<li><a href='/ui/proposals/{proposal.id}'>Proposal pack</a> · {esc(proposal.proposal_type.replace('_', ' '))} · {esc(proposal.status)}</li>"
            for proposal in proposals
        )
        or "<li>No proposal pack yet.</li>"
    )
    event_html = (
        "".join(
            f"<li>{esc(event.event_type)} · {esc(event.occurred_at)} · {esc(event.summary)}</li>" for event in events
        )
        or "<li>None</li>"
    )
    comment_html = (
        "".join(f"<li>{esc(comment.body)} · {esc(comment.created_at)}</li>" for comment in comments) or "<li>None</li>"
    )
    operators = db.scalars(select(Operator).where(Operator.active.is_(True))).all()
    operator_options = "".join(f"<option value='{op.id}'>{esc(op.display_name)}</option>" for op in operators)
    pilot = pilot_for_business(db, business.id)
    score_components = (
        db.scalars(select(OpportunityComponent).where(OpportunityComponent.opportunity_score_id == score.id)).all()
        if score
        else []
    )
    score_holds = (
        db.scalars(select(OpportunityHold).where(OpportunityHold.opportunity_score_id == score.id)).all()
        if score
        else []
    )
    latest_audit = db.scalar(
        select(AuditRun).where(AuditRun.business_id == business_id).order_by(AuditRun.completed_at.desc())
    )
    action_labels = {
        "generate_demo": (
            "Generate a concept demo",
            "The evidence is strong enough to prepare a safe, independent concept preview.",
        ),
        "conversion_upgrade_offer": (
            "Review a conversion upgrade",
            "The current site is usable, but there are specific ways to make it easier for customers to take action.",
        ),
        "technical_cleanup_offer": (
            "Review a technical cleanup",
            "The opportunity is focused on technical, accessibility, or SEO hygiene rather than a full rebuild.",
        ),
        "score_only": (
            "Keep this lead in review",
            "The business already has a functioning digital presence. No rebuild demo is recommended right now.",
        ),
        "audit_required": (
            "Run the website audit",
            "A website is present, but the evidence is not complete enough to recommend the next step.",
        ),
        "manual_review": (
            "Manual review required",
            "Identity or evidence needs an operator decision before any further action.",
        ),
        "do_not_contact": ("Do not contact", "A suppression or policy hold blocks outreach."),
    }
    raw_action = score.recommended_next_action if score else (brief.recommended_next_action if brief else None)
    action_title, action_reason = action_labels.get(
        raw_action or "", ("Review this business", "Collect more evidence before choosing the next step.")
    )
    band = score.band.title() if score else "Not scored"
    score_value = str(score.score) if score else "—"
    score_explanation = {
        "low": "Lower addressable opportunity based on the evidence collected.",
        "medium": "Some addressable gaps are present, with enough evidence for a focused next step.",
        "high": "Significant addressable gaps are present and the evidence supports a concrete next step.",
    }.get(score.band if score else "", "A score will appear after scoring completes.")

    def component_label(code: str) -> str:
        labels = {
            "NO_CLICK_TO_CALL": "No click-to-call path",
            "MISSING_H1": "Missing primary page heading",
            "LOW_IMAGE_ALT_COVERAGE": "Some images lack useful alternative text",
            "MISSING_VIEWPORT_META": "Missing mobile viewport setting",
            "NO_BOOKING_PATH": "No booking path detected",
            "NO_WHATSAPP_CTA": "No WhatsApp action detected",
            "WEBSITE_HEALTHY_REDUCES_GAP": "Healthy website reduces rebuild need",
            "VERIFIED_PHONE": "Phone contact verified",
            "FACTS_FOR_DEMO": "Enough verified facts for a demo",
        }
        return labels.get(code, code.replace("_", " ").title())

    component_rows = (
        "".join(
            f"<li><strong>{esc(component_label(c.code))}</strong><span>{c.points:+d} points</span><small>{esc(c.category.replace('_', ' ').title())} · {esc(c.source_type)}</small></li>"
            for c in score_components
        )
        or "<li><strong>No score components yet</strong><small>Run scoring to see the evidence behind the recommendation.</small></li>"
    )
    hold_notice = (
        "<div class='warning'><strong>Hold:</strong> " + "; ".join(esc(h.reason) for h in score_holds) + "</div>"
        if score_holds
        else "<p class='success'>No identity, suppression, or policy holds are blocking this lead.</p>"
    )
    observability = (
        f"<details class='detail-disclosure'><summary>Score details and evidence</summary>"
        f"<p class='muted'>These are scoring inputs, not judgments about how well the business is run. The score is deterministic and based only on collected evidence.</p>"
        f"<div class='score-breakdown'><div><span>Addressable opportunity</span><strong>{sum(c.points for c in score_components if c.category == 'addressable_gap'):+d}</strong></div><div><span>Commercial readiness</span><strong>{sum(c.points for c in score_components if c.category == 'commercial_readiness'):+d}</strong></div><div><span>Reachability</span><strong>{sum(c.points for c in score_components if c.category == 'reachability'):+d}</strong></div><div><span>Demo confidence</span><strong>{sum(c.points for c in score_components if c.category == 'demo_confidence'):+d}</strong></div></div>"
        f"<h3>Evidence components</h3><ul class='component-list'>{component_rows}</ul><h3>Holds</h3>{hold_notice}"
        f"<p class='muted'>Internal record references are intentionally hidden from the main view. Audit: {'available' if latest_audit else 'not run'} · Brief: {'available' if brief else 'not created'}.</p></details>"
    )
    pilot_banner = ""
    if pilot is not None:
        pilot_banner = f"<div class='safety'>{'DRY RUN MODE — manual outreach and CRM outcome logging are blocked by the operator console.' if pilot.mode == 'dry_run' else 'ACTIVE PILOT MODE — manual records represent operator activity; LBOE still sends nothing.'} <a href='/ui/pilots/{pilot.id}'>View pilot</a></div>"
    next_action_button = ""
    # A demo is generated from a persisted Business Brief. Keep the UI honest
    # about that prerequisite instead of showing a demo action that can only
    # return ``brief_required`` from the API.
    if raw_action == "audit_required" and latest_audit is None:
        next_action_button = f"<form method='post' action='/ui/businesses/{business_id}/action'><input type='hidden' name='action' value='audit'><button class='button-primary'>Run website audit</button></form>"
    elif brief is None:
        next_action_button = f"<form method='post' action='/ui/businesses/{business_id}/action'><input type='hidden' name='action' value='brief'><button class='button-primary'>Prepare business brief</button></form>"
    elif raw_action in {"conversion_upgrade_offer", "technical_cleanup_offer", "generate_demo"}:
        action_value = "generate_demo"
        action_label = "Generate concept preview"
        if raw_action == "conversion_upgrade_offer":
            action_label = "Generate conversion concept"
        elif raw_action == "technical_cleanup_offer":
            action_label = "Generate cleanup concept"
        next_action_button = f"<form method='post' action='/ui/businesses/{business_id}/action'><input type='hidden' name='action' value='{action_value}'><button class='button-primary'>{action_label}</button></form>"
    elif score is None:
        next_action_button = f"<form method='post' action='/ui/businesses/{business_id}/action'><input type='hidden' name='action' value='score'><button class='button-primary'>Score this lead</button></form>"
    elif any(demo.status == "approved" for demo in demos) and not proposals:
        next_action_button = f"<form method='post' action='/ui/businesses/{business_id}/action'><input type='hidden' name='action' value='proposal'><button class='button-primary'>Create proposal pack</button></form>"
    body = (
        pilot_banner
        + (
            f"<div class='success'>Action completed: {esc(action_completed.replace('_', ' '))}.</div>"
            if action_completed
            else ""
        )
        + (f"<div class='warning'>Action could not be completed: {esc(action_error)}</div>" if action_error else "")
        + f"<div class='page-intro'><div><div class='eyebrow'>Business workspace</div><h1>{esc(business.display_name)}</h1><p class='muted'>{esc(business.category or 'Local business')} · {esc(business.locality or 'Location not verified')}</p></div><span class='badge'>{esc(business.state.replace('_', ' ').title())}</span></div>"
        + f"<section class='next-action'><div><div class='eyebrow'>Recommended next step</div><h2>{esc(action_title)}</h2><p>{esc(action_reason)}</p></div>{next_action_button}</section>"
        + f"<div class='cards'><div class='card'><span>Opportunity score</span><b>{score_value}</b><small>{esc(band)} · {esc(score_explanation)}</small></div><div class='card'><span>Evidence status</span><b>{'Ready' if score and brief else 'In progress'}</b><small>{'Score and brief available' if score and brief else 'More evidence may be needed'}</small></div><div class='card'><span>Outreach</span><b>{'Drafted' if package else 'Not started'}</b><small>{'No messages are sent by LBOE'}</small></div></div>"
        + f"<section class='section'><div class='section-head'><h2>What we know</h2><span class='badge'>Verified identity</span></div><p><strong>{esc(business.display_name)}</strong> is listed as a <strong>{esc(business.category or 'local business')}</strong> in <strong>{esc(business.locality or 'an unverified location')}</strong>.</p><p class='muted'>{esc(business.address_text or 'A full address has not been verified yet.')}</p><p class='muted'>This page summarizes evidence collected by LBOE. It does not claim the business is poorly run.</p></section>"
        + f"<section class='section'><h2>Why this recommendation?</h2><p>{esc(brief.summary if brief else action_reason)}</p>{observability}</section>"
        + f"<section class='section'><h2>Evidence progress</h2><div class='stat-line'><span>Website / audit</span><strong>{'Audited' if latest_audit else 'Not audited'}</strong></div><div class='stat-line'><span>Business brief</span><strong>{'Prepared' if brief else 'Not prepared'}</strong></div><div class='stat-line'><span>Optional enrichment</span><strong>{'Available' if enrichment_runs else 'Not run'}</strong></div><p class='muted'>Enrichment is optional. “Not run” is not an error; the current recommendation can still be based on discovery and audit evidence.</p></section>"
        + f"<section class='section'><h2>Demo and proposal path</h2><p>{esc(package.status.replace('_', ' ').title()) if package else 'No outreach draft has been prepared.'}</p><ul>{demo_html}</ul><h3>Proposal packs</h3><ul>{proposal_html}</ul><p class='muted'>For a no-website lead, generate a concept preview first. After human approval, create a proposal pack for operator review. LBOE does not send messages automatically.</p></section>"
        + f"<section class='section'><h2>Activity</h2><h3>CRM events</h3><ul>{event_html}</ul><h3>Assignments</h3><ul>{''.join(f'<li>{esc(str(a.operator_id))} · {esc(a.status)}</li>' for a in assignments) or '<li>None</li>'}</ul><form method='post' action='/ui/businesses/{business_id}/assign'><select name='operator_id'>{operator_options}</select><button>Assign</button></form></section>"
        + f"<section class='section'><h2>Operator notes</h2><ul>{comment_html}</ul><form method='post' action='/ui/businesses/{business_id}/comment'><textarea name='body' required placeholder='Add context for the next operator'></textarea><button>Add note</button></form></section>"
        + f"<section class='section'><h2>Safety</h2><p class='muted'>Suppressing a business prevents future outreach actions and is recorded for auditability.</p><form method='post' action='/ui/businesses/{business_id}/suppress'><input name='reason' required placeholder='Suppression reason'><button>Suppress business</button></form></section>"
    )
    return page(business.display_name, body)


@router.post("/ui/businesses/{business_id}/action")
async def business_action(
    business_id: uuid.UUID, action: str = Form(...), db: Session = Depends(session)
) -> RedirectResponse:
    """Run one explicit, safe operator action and return to the business workspace."""
    from lboe_api.main import (
        AuditRequestBody,
        ScoreRequestBody,
        audit_business,
        create_brief,
        create_demo,
        create_proposal,
        score_business,
    )

    if db.get(Business, business_id) is None:
        raise HTTPException(404, "business_not_found")
    try:
        if action == "score":
            await score_business(business_id, ScoreRequestBody(idempotency_key="ui"), db)
        elif action == "audit":
            await audit_business(
                business_id,
                AuditRequestBody(timeout_seconds=30, max_pages=2, idempotency_key="ui"),
                db,
            )
        elif action == "brief":
            await create_brief(business_id, {"idempotency_key": "ui"}, db)
        elif action == "generate_demo":
            result = create_demo(business_id, {"idempotency_key": "ui"}, db)
            if result.get("status") == "not_demo_eligible":
                reason = str(result.get("reason") or "not_demo_eligible").replace("_", " ")
                return RedirectResponse(
                    f"/ui/businesses/{business_id}?action_error={quote_plus(f'Demo not available: {reason}')}",
                    status_code=303,
                )
        elif action == "proposal":
            create_proposal(business_id, {"idempotency_key": "ui"}, db)
        else:
            raise HTTPException(422, "unsupported_business_action")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return RedirectResponse(f"/ui/businesses/{business_id}?action_error={quote_plus(detail)}", status_code=303)
    return RedirectResponse(f"/ui/businesses/{business_id}?action_completed={quote_plus(action)}", status_code=303)


@router.get("/ui/businesses/{business_id}/outreach-workbench", response_class=HTMLResponse)
def outreach_workbench(business_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(404, "business_not_found")
    package = db.scalar(
        select(OutreachDraftPackage)
        .where(OutreachDraftPackage.business_id == business_id)
        .order_by(OutreachDraftPackage.created_at.desc())
    )
    messages: list[OutreachDraftMessage] = []
    if package:
        messages = list(
            db.scalars(select(OutreachDraftMessage).where(OutreachDraftMessage.package_id == package.id)).all()
        )
    followups = db.scalars(
        select(ManualFollowUpTask)
        .where(ManualFollowUpTask.business_id == business_id)
        .order_by(ManualFollowUpTask.due_at)
    ).all()
    objections = db.scalars(
        select(OutreachObjection)
        .where(OutreachObjection.business_id == business_id)
        .order_by(OutreachObjection.created_at.desc())
    ).all()
    drafts = (
        "".join(
            f"<article><h3>{esc(item.channel)}</h3><p>{esc(item.subject or '')}</p><pre>{esc(item.body)}</pre><button type='button' onclick='navigator.clipboard.writeText(this.previousElementSibling.textContent)'>Copy draft</button></article>"
            for item in messages
        )
        or "<p>No draft package.</p>"
    )
    followup_html = (
        "".join(f"<li>{esc(item.due_at)} · {esc(item.reason)} · {esc(item.status)}</li>" for item in followups)
        or "<li>None</li>"
    )
    objection_html = "".join(f"<li>{esc(item.code)} · {esc(item.notes)}</li>" for item in objections) or "<li>None</li>"
    return page(
        "Manual outreach workbench",
        f"<div class='safety'>COPY ONLY — LBOE never sends messages. Perform any contact outside LBOE and record it manually.</div><p>{esc(business.display_name)} · state {esc(business.state)}</p><h2>Drafts</h2>{drafts}<h2>Follow-up list</h2><ul>{followup_html}</ul><h2>Objections</h2><ul>{objection_html}</ul><p>Use the API to add follow-up tasks and operator-entered objection or reply classifications.</p>",
    )


@router.get("/ui/queues/follow-up", response_class=HTMLResponse)
def follow_up_queue(db: Session = Depends(session)) -> HTMLResponse:
    tasks = db.scalars(
        select(ManualFollowUpTask).where(ManualFollowUpTask.status == "open").order_by(ManualFollowUpTask.due_at)
    ).all()
    rows = (
        "".join(
            f"<tr><td><a href='/ui/businesses/{item.business_id}/outreach-workbench'>{item.business_id}</a></td><td>{esc(item.due_at)}</td><td>{esc(item.reason)}</td></tr>"
            for item in tasks
        )
        or "<tr><td colspan='3'>No open follow-ups</td></tr>"
    )
    return page(
        "Follow-up queue",
        f"<p>Local operator list only. No reminders or messages are sent.</p><table><tr><th>Business</th><th>Due</th><th>Reason</th></tr>{rows}</table>",
    )


@router.post("/ui/businesses/{business_id}/assign")
def assign_business(
    business_id: uuid.UUID, operator_id: uuid.UUID = Form(...), db: Session = Depends(session)
) -> RedirectResponse:
    if db.get(Business, business_id) is None or db.get(Operator, operator_id) is None:
        raise HTTPException(404, "business_or_operator_not_found")
    db.add(OperatorAssignment(business_id=business_id, operator_id=operator_id, status="assigned"))
    db.add(
        OperatorAuditEvent(
            operator_id=operator_id,
            business_id=business_id,
            entity_type="assignment",
            entity_id=business_id,
            action="assigned",
            after_data={"operator_id": str(operator_id)},
        )
    )
    db.commit()
    return RedirectResponse(f"/ui/businesses/{business_id}", status_code=303)


@router.post("/ui/businesses/{business_id}/comment")
def add_comment(business_id: uuid.UUID, body: str = Form(...), db: Session = Depends(session)) -> RedirectResponse:
    operator = db.scalar(select(Operator).where(Operator.active.is_(True)).order_by(Operator.created_at))
    if operator is None:
        operator = Operator(display_name="local-operator", role="owner")
        db.add(operator)
        db.flush()
    db.add(OperatorComment(business_id=business_id, operator_id=operator.id, body=body, comment_type="general"))
    db.add(
        OperatorAuditEvent(
            operator_id=operator.id,
            business_id=business_id,
            entity_type="business",
            entity_id=business_id,
            action="comment_added",
            event_metadata={"ui": True},
        )
    )
    db.commit()
    return RedirectResponse(f"/ui/businesses/{business_id}", status_code=303)


@router.post("/ui/businesses/{business_id}/suppress")
def suppress(business_id: uuid.UUID, reason: str = Form(...), db: Session = Depends(session)) -> RedirectResponse:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(404, "business_not_found")
    if business.state != "SUPPRESSED":
        business.state = "SUPPRESSED"
    db.add(SuppressionEntry(business_id=business_id, reason=reason))
    db.add(
        OperatorAuditEvent(
            business_id=business_id,
            entity_type="business",
            entity_id=business_id,
            action="suppressed_from_ui",
            after_data={"state": "SUPPRESSED"},
        )
    )
    db.commit()
    return RedirectResponse(f"/ui/businesses/{business_id}", status_code=303)


@router.get("/ui/reports/pilot", response_class=HTMLResponse)
def report(db: Session = Depends(session)) -> HTMLResponse:
    data = build_pilot_report(db, include_details=True)
    quality = "".join(
        f"<tr><td>{esc(item['code'])}</td><td>{item['count']}</td></tr>" for item in data["quality_metrics"]
    )
    return page(
        "Global pilot report",
        metric_cards(data)
        + f"<h2>Quality metrics</h2><table><tr><th>Metric</th><th>Count</th></tr>{quality}</table><p>System delivery count: <strong>0</strong></p>",
    )


@router.get("/ui/campaigns/{campaign_id}/reports/pilot", response_class=HTMLResponse)
def campaign_report(campaign_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    data = build_pilot_report(db, campaign_id=campaign_id, include_details=True)
    return page(
        "Campaign pilot report",
        metric_cards(data)
        + f"<p>Campaign: {esc(campaign_id)} · System delivery count: <strong>0</strong></p><pre>{esc(data.get('details', {}))}</pre>",
    )


@router.get("/ui/queues", response_class=HTMLResponse)
def queues(db: Session = Depends(session)) -> HTMLResponse:
    links = [
        (
            "demo-review",
            "Demo review",
            select(GeneratedDemo).where(GeneratedDemo.status.in_(["qa_passed", "review_pending"])),
        ),
        ("outreach-draft", "Outreach drafts", select(Business).where(Business.state == "APPROVED_FOR_OUTREACH")),
        ("readiness", "Readiness", select(OutreachDraftPackage).where(OutreachDraftPackage.status == "ready")),
        ("manual-contact", "Manual contact", select(Business).where(Business.state == "OUTREACH_READY")),
        (
            "crm-followup",
            "CRM follow-up",
            select(Business).where(Business.state.in_(["CONTACTED", "REPLIED", "MEETING", "PROPOSAL"])),
        ),
        (
            "no-website",
            "No website opportunities",
            select(Business).where(
                ~exists().where(Contact.business_id == Business.id, Contact.channel == "website"),
                Business.state.not_in(["SUPPRESSED", "ARCHIVED"]),
            ),
        ),
    ]
    body = (
        "<div class='queue-grid'>"
        + "".join(
            f"<a class='card' href='/ui/queues/{slug}'><b>{label}</b><span>{len(db.scalars(query).all())} items</span></a>"  # type: ignore[call-overload]
            for slug, label, query in links
        )
        + "</div>"
    )
    return page("Queues", body)


@router.get("/ui/queues/{queue_name}", response_class=HTMLResponse)
def queue_detail(queue_name: str, db: Session = Depends(session)) -> HTMLResponse:
    if queue_name == "no-website":
        return no_website_queue(db)
    if queue_name == "no-demo-reason":
        return no_demo_reason_queue(db)
    if queue_name == "qa-failed":
        return qa_failed_queue(db)
    if queue_name == "not-outreach-ready":
        return not_outreach_ready_queue(db)
    if queue_name == "weak-evidence":
        return weak_evidence_queue(db)
    if queue_name == "proposal-ready":
        return proposal_ready_queue(db)
    if queue_name == "delivery":
        return delivery_queue(db)
    mapping = {
        "demo-review": (
            "Demo review",
            select(GeneratedDemo).where(GeneratedDemo.status.in_(["qa_passed", "review_pending"])),
        ),
        "outreach-draft": ("Outreach drafts", select(Business).where(Business.state == "APPROVED_FOR_OUTREACH")),
        "readiness": ("Readiness", select(OutreachDraftPackage).where(OutreachDraftPackage.status == "ready")),
        "manual-contact": ("Manual contact", select(Business).where(Business.state == "OUTREACH_READY")),
        "crm-followup": (
            "CRM follow-up",
            select(Business).where(Business.state.in_(["CONTACTED", "REPLIED", "MEETING", "PROPOSAL"])),
        ),
        "no-website": (
            "No website opportunities",
            select(Business).where(
                ~exists().where(Contact.business_id == Business.id, Contact.channel == "website"),
                Business.state.not_in(["SUPPRESSED", "ARCHIVED"]),
            ),
        ),
    }
    if queue_name not in mapping:
        raise HTTPException(404, "queue_not_found")
    title, query = mapping[queue_name]
    items = db.scalars(query).all()  # type: ignore[call-overload]
    rows = []
    for item in items:
        # Some queues query the business directly; others query a related
        # record (demo, draft, or readiness package) with business_id.
        business_id = getattr(item, "business_id", item.id)
        business = db.get(Business, business_id)
        rows.append(
            f"<li><a href='/ui/businesses/{business_id}'>{esc(business.display_name if business else business_id)}</a></li>"
        )
    return page(title, "<ul>" + "".join(rows) + "</ul>")


def _reason_queue(title: str, items: list[tuple[Business, str, str]]) -> HTMLResponse:
    rows = (
        "".join(
            f"<tr><td><a href='/ui/businesses/{b.id}'>{esc(b.display_name)}</a></td><td>{esc(b.state)}</td><td>{esc(reason)}</td><td>{esc(next_action)}</td></tr>"
            for b, reason, next_action in items
        )
        or "<tr><td colspan='4'>No items</td></tr>"
    )
    return page(
        title,
        "<table><tr><th>Business</th><th>State</th><th>Blocking reason</th><th>Safe next action</th></tr>"
        + rows
        + "</table>",
    )


def no_website_queue(db: Session) -> HTMLResponse:
    """Prioritized queue for the primary acquisition use case."""
    businesses = db.scalars(
        select(Business)
        .where(
            ~exists().where(Contact.business_id == Business.id, Contact.channel == "website"),
            Business.state.not_in(["SUPPRESSED", "ARCHIVED"]),
        )
        .order_by(Business.created_at.desc())
    ).all()
    rows: list[str] = []
    seen: set[tuple[str, str | None]] = set()
    for business in businesses:
        key = (business.display_name.strip().lower(), (business.locality or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        score = db.scalar(
            select(OpportunityScore)
            .where(OpportunityScore.business_id == business.id)
            .order_by(OpportunityScore.created_at.desc())
        )
        brief = db.scalar(
            select(BusinessBrief)
            .where(BusinessBrief.business_id == business.id)
            .order_by(BusinessBrief.created_at.desc())
        )
        action = brief.recommended_next_action.replace("_", " ") if brief else "score this lead"
        rows.append(
            f"<tr><td><a class='table-primary' href='/ui/businesses/{business.id}'>{esc(business.display_name)}</a><small class='table-sub'>{esc(business.locality or 'Location not verified')}</small></td><td><span class='badge'>{esc(business.state.replace('_', ' ').title())}</span></td><td>{score.score if score else '—'}</td><td>{esc(action)}</td><td><a class='button button-small button-secondary' href='/ui/businesses/{business.id}'>Review lead</a></td></tr>"
        )
    table = (
        "<table><tr><th>Business</th><th>State</th><th>Score</th><th>Recommended next step</th><th></th></tr>"
        + ("".join(rows) or "<tr><td colspan='5'>No active businesses without a website were found.</td></tr>")
        + "</table>"
    )
    return page(
        "No website opportunities",
        "<div class='page-intro'><div><span class='eyebrow'>Primary acquisition queue</span><h1>No website opportunities</h1><p class='muted'>These active businesses have no website contact recorded. Review the facts, score the lead, and prepare a starter website concept when eligible.</p></div><span class='badge'>"
        + str(len(rows))
        + " unique leads</span></div>"
        + table,
    )


@router.get("/ui/queues/no-demo-reason", response_class=HTMLResponse)
def no_demo_reason_queue(db: Session = Depends(session)) -> HTMLResponse:
    items = []
    for business in db.scalars(select(Business)).all():
        score = db.scalar(
            select(OpportunityScore)
            .where(OpportunityScore.business_id == business.id)
            .order_by(OpportunityScore.created_at.desc())
        )
        demo = db.scalar(
            select(GeneratedDemo)
            .where(GeneratedDemo.business_id == business.id)
            .order_by(GeneratedDemo.created_at.desc())
        )
        if score and demo is None:
            items.append((business, score.recommended_next_action, "audit, manual review, or score-only follow-up"))
    return _reason_queue("Why no demo", items)


@router.get("/ui/queues/qa-failed", response_class=HTMLResponse)
def qa_failed_queue(db: Session = Depends(session)) -> HTMLResponse:
    items = []
    for demo in db.scalars(select(GeneratedDemo).where(GeneratedDemo.status == "qa_failed")).all():
        business = db.get(Business, demo.business_id)
        if business:
            qa = db.scalar(select(DemoQaRun).where(DemoQaRun.demo_id == demo.id).order_by(DemoQaRun.created_at.desc()))
            failed = (
                ", ".join(str(k) for k, v in (qa.checks if qa else {}).items() if v is False)
                or "QA failed; inspect stored checks"
            )
            items.append((business, failed, "regenerate or mark manual edit; do not share"))
    return _reason_queue("QA-failed demos", items)


@router.get("/ui/queues/not-outreach-ready", response_class=HTMLResponse)
def not_outreach_ready_queue(db: Session = Depends(session)) -> HTMLResponse:
    items = []
    for business in db.scalars(select(Business)).all():
        if business.state in {"APPROVED_FOR_OUTREACH", "CONSENT_PENDING"}:
            items.append(
                (business, "consent/readiness not complete", "review draft, consent basis, and suppression gates")
            )
    return _reason_queue("Not outreach-ready", items)


@router.get("/ui/queues/weak-evidence", response_class=HTMLResponse)
def weak_evidence_queue(db: Session = Depends(session)) -> HTMLResponse:
    items = []
    for business in db.scalars(select(Business)).all():
        score = db.scalar(
            select(OpportunityScore)
            .where(OpportunityScore.business_id == business.id)
            .order_by(OpportunityScore.created_at.desc())
        )
        if score and score.recommended_next_action in {"manual_review", "audit_required", "score_only"}:
            items.append((business, score.recommended_next_action, "verify business-owned evidence before any demo"))
    return _reason_queue("Weak evidence", items)


@router.post("/ui/bulk", response_class=HTMLResponse)
def bulk_action(
    action: str = Form(...),
    business_ids: list[str] = Form(default=[]),
    confirm: bool = Form(False),
    db: Session = Depends(session),
) -> HTMLResponse:
    allowed = {"score", "brief", "demo", "suppress"}
    if action not in allowed:
        raise HTTPException(422, "unsupported_bulk_action")
    ids = [uuid.UUID(value) for value in business_ids]
    businesses: list[Business] = []
    for value in ids:
        business = db.get(Business, value)
        if business is not None:
            businesses.append(business)
    blocked = []
    eligible = []
    for business in businesses:
        if action == "suppress" or business.state not in {"SUPPRESSED", "ARCHIVED"}:
            eligible.append(business)
        else:
            blocked.append(f"{business.display_name}: suppressed/archive state")
    if confirm and action == "suppress":
        for business in eligible:
            business.state = "SUPPRESSED"
            db.add(SuppressionEntry(business_id=business.id, reason="Bulk operator suppression"))
        db.commit()
    mode = "executed" if confirm and action == "suppress" else "dry-run"
    return page(
        "Bulk action result",
        f"<p>{esc(mode)} · action={esc(action)}</p><p>Eligible: {len(eligible)} · blocked: {len(blocked)}</p><ul>{''.join(f'<li>{esc(item)}</li>' for item in blocked) or '<li>No blocked items</li>'}</ul><p>Score, brief, and demo bulk actions require per-item backend calls; approval, readiness, contact logging, and CRM actions are never bulk-enabled.</p>",
    )


@router.get("/ui/operators", response_class=HTMLResponse)
def operators(db: Session = Depends(session)) -> HTMLResponse:
    rows = "".join(
        f"<tr><td>{esc(op.display_name)}</td><td>{esc(op.role)}</td><td>{'active' if op.active else 'inactive'}</td></tr>"
        for op in db.scalars(select(Operator).order_by(Operator.display_name)).all()
    )
    form = "<h2>Add local operator</h2><form method='post' action='/ui/operators'><input name='display_name' required placeholder='Display name'><input name='role' value='operator'><button>Create</button></form>"
    return page(
        "Operators",
        f"<table><tr><th>Name</th><th>Role</th><th>Status</th></tr>{rows}</table>{form}<p>Local trusted operator mode. No external authentication is configured.</p>",
    )


@router.post("/ui/operators")
def create_operator(
    display_name: str = Form(...), role: str = Form("operator"), db: Session = Depends(session)
) -> RedirectResponse:
    if role not in {"owner", "manager", "operator", "reviewer", "viewer"}:
        raise HTTPException(422, "invalid_operator_role")
    db.add(Operator(display_name=display_name, role=role))
    db.commit()
    return RedirectResponse("/ui/operators", status_code=303)


@router.get("/ui/operator/select", response_class=HTMLResponse)
def select_operator(db: Session = Depends(session)) -> HTMLResponse:
    options = "".join(
        f"<option value='{op.id}'>{esc(op.display_name)} ({esc(op.role)})</option>"
        for op in db.scalars(select(Operator).where(Operator.active.is_(True))).all()
    )
    return page(
        "Select operator",
        f"<form method='post'><select name='operator_id'>{options}</select><button>Use local operator</button></form>",
    )


@router.post("/ui/operator/select")
def set_operator(operator_id: uuid.UUID = Form(...)) -> RedirectResponse:
    response = RedirectResponse("/ui", status_code=303)
    response.set_cookie("lboe_operator_id", str(operator_id), httponly=True, samesite="lax")
    return response


@router.get("/ui/my-queue", response_class=HTMLResponse)
def my_queue(request: Request, db: Session = Depends(session)) -> Response:
    operator_id = request.cookies.get("lboe_operator_id")
    if not operator_id:
        return RedirectResponse("/ui/operator/select", status_code=303)
    assignments = db.scalars(
        select(OperatorAssignment).where(
            OperatorAssignment.operator_id == uuid.UUID(operator_id),
            OperatorAssignment.status.in_(["assigned", "in_progress"]),
        )
    ).all()
    rows = (
        "".join(
            f"<li><a href='/ui/businesses/{assignment.business_id}'>{assignment.business_id}</a> · {assignment.status}</li>"
            for assignment in assignments
        )
        or "<li>No assigned leads</li>"
    )
    return page("My queue", f"<ul>{rows}</ul>")


def safe_demo_path(demo: GeneratedDemo, db: Session) -> Path:
    artifact = db.scalar(select(DemoArtifact).where(DemoArtifact.demo_id == demo.id, DemoArtifact.kind == "index"))
    if artifact is None:
        raise HTTPException(404, "demo_artifact_not_found")
    root = Path(settings.demo_artifact_root).resolve()
    path = Path(artifact.path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "demo_artifact_unavailable")
    return path


@router.get("/ui/demos/{demo_id}/preview", response_class=HTMLResponse)
def internal_preview(demo_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    demo = db.get(GeneratedDemo, demo_id)
    if demo is None:
        raise HTTPException(404, "demo_not_found")
    path = safe_demo_path(demo, db)
    content = path.read_text(encoding="utf-8")
    if DISCLAIMER not in content:
        content = f"<div class='safety'>{DISCLAIMER}</div>" + content
    return HTMLResponse(content)


@router.get("/ui/artifacts/demo/{demo_id}/index", response_class=HTMLResponse)
def demo_artifact_preview(demo_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    return internal_preview(demo_id, db)


@router.get("/ui/artifacts/audit/{artifact_id}")
def audit_artifact(artifact_id: uuid.UUID, db: Session = Depends(session)) -> Response:
    artifact = db.get(AuditArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "audit_artifact_not_found")
    root = Path(settings.audit_artifact_root).resolve()
    path = Path(artifact.path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "audit_artifact_unavailable")
    if artifact.mime_type.startswith("image/"):
        return Response(path.read_bytes(), media_type=artifact.mime_type)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/ui/demos/{demo_id}/qa", response_class=HTMLResponse)
def demo_qa_detail(demo_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    demo = db.get(GeneratedDemo, demo_id)
    if demo is None:
        raise HTTPException(404, "demo_not_found")
    qa = db.scalar(select(DemoQaRun).where(DemoQaRun.demo_id == demo_id).order_by(DemoQaRun.created_at.desc()))
    details = qa_explanations(qa.checks) if qa else []
    rows = (
        "".join(
            f"<tr><td>{esc(item['code'])}</td><td>{'pass' if item['passed'] else 'FAIL'}</td><td>{esc(item['severity'])}</td><td>{esc(item['explanation'])}</td><td>{esc(item['recommended_action'])}</td></tr>"
            for item in details
        )
        or "<tr><td colspan='5'>No QA run</td></tr>"
    )
    return page(
        "Demo QA",
        f"<p>Status: <strong>{esc(demo.status)}</strong>. Failed checks block sharing.</p><table><tr><th>Check</th><th>Result</th><th>Severity</th><th>Explanation</th><th>Action</th></tr>{rows}</table>",
    )


@router.get("/ui/demos/{demo_id}/preview-links", response_class=HTMLResponse)
def preview_links(demo_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    links = db.scalars(
        select(DemoPreviewLink).where(DemoPreviewLink.demo_id == demo_id).order_by(DemoPreviewLink.created_at.desc())
    ).all()
    rows = (
        "".join(
            f"<li>{esc(link.label)} · {esc(link.status)} · expires {esc(link.expires_at)} · "
            f"accesses {len(db.scalars(select(DemoPreviewAccessEvent).where(DemoPreviewAccessEvent.preview_link_id == link.id)).all())} "
            f"<form method='post' action='/ui/preview-links/{link.id}/revoke'><button>Revoke</button></form></li>"
            for link in links
        )
        or "<li>None</li>"
    )
    form = f"<form method='post' action='/ui/demos/{demo_id}/preview-links'><input name='label' value='Concept preview'><input name='expires_days' type='number' min='1' max='30' value='7'><button>Create external preview link</button></form><p>Only share QA-passed/approved concept previews. Not an official website.</p>"
    return page("Preview links", form + f"<ul>{rows}</ul>")


@router.post("/ui/demos/{demo_id}/preview-links")
def create_preview_link(
    demo_id: uuid.UUID,
    label: str = Form("Concept preview"),
    expires_days: int = Form(7),
    db: Session = Depends(session),
) -> HTMLResponse:
    demo = db.get(GeneratedDemo, demo_id)
    if demo is None or demo.status not in {"qa_passed", "approved"}:
        raise HTTPException(409, "demo_not_shareable")
    business = db.get(Business, demo.business_id)
    if business is None or business.state == "SUPPRESSED":
        raise HTTPException(409, "business_suppressed")
    pilot = pilot_for_business(db, business.id)
    if pilot is not None and not cap_available(db, pilot, "preview_link"):
        raise HTTPException(409, "pilot_preview_link_cap_reached")
    safe_demo_path(demo, db)
    raw = secrets.token_urlsafe(32)
    link = DemoPreviewLink(
        demo_id=demo.id,
        business_id=demo.business_id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        label=label,
        permission="external_view",
        expires_at=datetime.now(UTC) + timedelta(days=max(1, min(expires_days, 30))),
    )
    db.add(link)
    db.commit()
    return page(
        "Preview link created",
        f"<p>Copy this one-time token URL:</p><code>/preview/{esc(raw)}</code><p>Token is not stored in raw form. Save it now.</p>",
    )


@router.get("/preview/{token}")
def external_preview(token: str, request: Request, db: Session = Depends(session)) -> Response:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    link = db.scalar(select(DemoPreviewLink).where(DemoPreviewLink.token_hash == token_hash))
    if link is None:
        raise HTTPException(404, "preview_not_found")
    now = datetime.now(UTC)
    expires_at = link.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if link.status != "active" or (expires_at and expires_at < now):
        if link.status == "active" and expires_at and expires_at < now:
            link.status = "expired"
            db.commit()
        raise HTTPException(410, "preview_expired_or_revoked")
    demo = db.get(GeneratedDemo, link.demo_id)
    if demo is None:
        raise HTTPException(404, "demo_not_found")
    try:
        path = safe_demo_path(demo, db)
        content = path.read_text(encoding="utf-8")
        if DISCLAIMER not in content:
            content = f"<div class='safety'>{DISCLAIMER}</div>" + content
        db.add(DemoPreviewAccessEvent(preview_link_id=link.id, outcome="served", event_metadata={"external": True}))
        db.commit()
        return HTMLResponse(content)
    except HTTPException:
        db.add(DemoPreviewAccessEvent(preview_link_id=link.id, outcome="blocked", event_metadata={"external": True}))
        db.commit()
        raise


@router.post("/ui/preview-links/{link_id}/revoke")
def revoke_preview(link_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    link = db.get(DemoPreviewLink, link_id)
    if link is None:
        raise HTTPException(404, "preview_not_found")
    link.status = "revoked"
    link.revoked_at = datetime.now(UTC)
    db.commit()
    return RedirectResponse(f"/ui/demos/{link.demo_id}/preview-links", status_code=303)


def _pilot(db: Session, pilot_id: uuid.UUID) -> PilotRun:
    item = db.get(PilotRun, pilot_id)
    if item is None:
        raise HTTPException(404, "pilot_not_found")
    return item


@router.get("/ui/pilots", response_class=HTMLResponse)
def pilot_list(db: Session = Depends(session)) -> HTMLResponse:
    rows = (
        "".join(
            f"<tr><td><a href='/ui/pilots/{p.id}'>{esc(p.name)}</a></td><td>{esc(p.mode)}</td><td>{esc(p.status)}</td><td>{esc(p.vertical)}</td></tr>"
            for p in db.scalars(select(PilotRun).order_by(PilotRun.created_at.desc())).all()
        )
        or "<tr><td colspan='4'>No pilots</td></tr>"
    )
    return page(
        "Pilot operations",
        "<p><a class='button' href='/ui/pilots/new'>Create pilot</a></p><table><tr><th>Name</th><th>Mode</th><th>Status</th><th>Vertical</th></tr>"
        + rows
        + "</table>",
    )


@router.get("/ui/pilots/new", response_class=HTMLResponse)
def pilot_new(db: Session = Depends(session)) -> HTMLResponse:
    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    opts = "".join(f"<option value='{c.id}'>{esc(c.name)}</option>" for c in campaigns)
    form = f"<form method='post' action='/ui/pilots'><label>Name <input name='name' required></label><label>Campaign <select name='campaign_id'>{opts}</select></label><label>Mode <select name='mode'><option>dry_run</option><option>active</option></select></label><label>Target <input name='target_lead_count' type='number' value='10'></label><label>Max businesses <input name='max_businesses' type='number' value='50'></label><label>Daily demo cap <input name='daily_demo_cap' type='number' value='10'></label><label>Daily preview cap <input name='daily_preview_link_cap' type='number' value='10'></label><label>Daily contact cap <input name='daily_manual_contact_cap' type='number' value='5'></label><label>Daily readiness cap <input name='daily_readiness_approval_cap' type='number' value='5'></label><button>Create</button></form>"
    return page("Create pilot", form)


@router.post("/ui/pilots")
def pilot_create(
    name: str = Form(...),
    campaign_id: uuid.UUID = Form(...),
    mode: str = Form("dry_run"),
    target_lead_count: int = Form(10),
    max_businesses: int = Form(50),
    daily_demo_cap: int = Form(10),
    daily_preview_link_cap: int = Form(10),
    daily_manual_contact_cap: int = Form(5),
    daily_readiness_approval_cap: int = Form(5),
    db: Session = Depends(session),
) -> RedirectResponse:
    campaign = db.get(Campaign, campaign_id)
    if (
        campaign is None
        or mode not in {"dry_run", "active"}
        or min(
            target_lead_count,
            max_businesses,
            daily_demo_cap,
            daily_preview_link_cap,
            daily_manual_contact_cap,
            daily_readiness_approval_cap,
        )
        <= 0
    ):
        raise HTTPException(422, "invalid_pilot_config")
    p = PilotRun(
        name=name,
        campaign_id=campaign.id,
        vertical=campaign.vertical,
        geography=campaign.geography or "",
        target_lead_count=target_lead_count,
        mode=mode,
        status="draft",
        source_policy_version=POLICY_VERSION,
        default_preview_expiry_days=7,
        max_businesses=max_businesses,
        daily_demo_cap=daily_demo_cap,
        daily_preview_link_cap=daily_preview_link_cap,
        daily_manual_contact_cap=daily_manual_contact_cap,
        daily_readiness_approval_cap=daily_readiness_approval_cap,
    )
    db.add(p)
    db.flush()
    audit(db, p, "created", None, after={"status": "draft"})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}", status_code=303)


@router.get("/ui/pilots/{pilot_id}", response_class=HTMLResponse)
def pilot_detail(pilot_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = _pilot(db, pilot_id)
    c = counters(db, p)
    report = build_pilot_report(db, campaign_id=p.campaign_id)
    counts = {item["code"]: item["count"] for item in report["quality_metrics"]}
    banner = (
        "DRY RUN MODE — no real outreach should be logged."
        if p.mode == "dry_run"
        else "ACTIVE PILOT MODE — manual outreach records represent operator activity."
    )
    body = f"<div class='safety'>{banner}</div><p>Status: <strong>{p.status}</strong> · Mode: <strong>{p.mode}</strong></p><div class='cards'><div class='card'>Businesses {c['businesses']} / {p.max_businesses}</div><div class='card'>Audited {counts.get('audit_runs', 0)}</div><div class='card'>Scored {counts.get('score_count', 0)}</div><div class='card'>Briefs {counts.get('brief_count', 0)}</div><div class='card'>Demos {counts.get('demo_generated', 0)}</div><div class='card'>QA failed {counts.get('demo_qa_failed', 0)}</div><div class='card'>Approved demos {counts.get('approved_demos', 0)}</div><div class='card'>Outreach ready {next((x['count'] for x in report['funnel_metrics'] if x['stage'] == 'OUTREACH_READY'), 0)}</div><div class='card'>Demos today {c['demos_today']} / {p.daily_demo_cap}</div><div class='card'>Preview links {c['preview_links_today']} / {p.daily_preview_link_cap}</div><div class='card'>Contacts {c['manual_contacts_today']} / {p.daily_manual_contact_cap}</div><div class='card'>System delivery 0</div></div><p><a class='button' href='/ui/pilots/{p.id}/readiness'>Readiness</a> <a class='button' href='/ui/pilots/{p.id}/calibration'>Calibration</a> <a class='button' href='/ui/pilots/{p.id}/exports'>Exports</a> <a class='button' href='/ui/pilots/{p.id}/retrospective'>Retrospective</a></p>"
    if p.status == "draft":
        body += f"<form method='post' action='/ui/pilots/{p.id}/mark-ready'><button>Mark ready</button></form>"
    if p.status == "ready":
        body += f"<form method='post' action='/ui/pilots/{p.id}/activate'><button>Activate</button></form>"
    if p.status == "active":
        body += f"<form method='post' action='/ui/pilots/{p.id}/pause'><button>Pause</button></form>"
    if p.status != "closed":
        body += f"<form method='post' action='/ui/pilots/{p.id}/close'><button>Close pilot</button></form>"
    return page(p.name, body)


@router.post("/ui/pilots/{pilot_id}/update")
def pilot_update(
    pilot_id: uuid.UUID,
    name: str = Form(...),
    target_lead_count: int = Form(...),
    max_businesses: int = Form(...),
    daily_demo_cap: int = Form(...),
    daily_preview_link_cap: int = Form(...),
    daily_manual_contact_cap: int = Form(...),
    daily_readiness_approval_cap: int = Form(...),
    db: Session = Depends(session),
) -> RedirectResponse:
    pilot = _pilot(db, pilot_id)
    if (
        pilot.status == "closed"
        or min(
            target_lead_count,
            max_businesses,
            daily_demo_cap,
            daily_preview_link_cap,
            daily_manual_contact_cap,
            daily_readiness_approval_cap,
        )
        <= 0
    ):
        raise HTTPException(409, "pilot_not_mutable")
    pilot.name = name
    pilot.target_lead_count = target_lead_count
    pilot.max_businesses = max_businesses
    pilot.daily_demo_cap = daily_demo_cap
    pilot.daily_preview_link_cap = daily_preview_link_cap
    pilot.daily_manual_contact_cap = daily_manual_contact_cap
    pilot.daily_readiness_approval_cap = daily_readiness_approval_cap
    pilot.updated_at = datetime.now(UTC)
    audit(db, pilot, "updated", None, after={"name": name, "caps": True})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{pilot.id}", status_code=303)


@router.get("/ui/pilots/{pilot_id}/calibration", response_class=HTMLResponse)
def pilot_calibration(pilot_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    pilot = _pilot(db, pilot_id)
    report = build_pilot_report(db, campaign_id=pilot.campaign_id, include_details=True)
    quality = {item["code"]: item["count"] for item in report["quality_metrics"]}
    rows = "".join(
        f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>"
        for key, value in sorted(quality.items())
        if key.startswith(("score_band:", "score_action:", "audit_finding:"))
    )
    return page(
        "Pilot calibration",
        f"<p>Read-only calibration view for {esc(pilot.name)}. Use evidence to adjust future weights; do not interpret score as business quality.</p><table><tr><th>Signal</th><th>Count</th></tr>{rows}</table><p>QA failures must be reviewed before sharing. No automated sending is available.</p>",
    )


@router.get("/ui/reports/calibration", response_class=HTMLResponse)
def calibration_report(db: Session = Depends(session)) -> HTMLResponse:
    report = build_pilot_report(db, include_details=True)
    quality = {item["code"]: item["count"] for item in report["quality_metrics"]}
    rows = "".join(
        f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>"
        for key, value in sorted(quality.items())
        if key.startswith(("score_band:", "score_action:", "audit_finding:"))
    )
    return page(
        "Calibration report",
        f"<p>Deterministic pilot evidence only; score is not business quality.</p><table><tr><th>Signal</th><th>Count</th></tr>{rows}</table><p>Review weak evidence and QA failures before changing weights.</p>",
    )


@router.get("/ui/pilots/{pilot_id}/readiness", response_class=HTMLResponse)
def pilot_readiness(pilot_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = _pilot(db, pilot_id)
    summary = readiness_summary(db, p, settings)
    rows = "".join(
        f"<tr><td>{esc(c['label'])}</td><td>{c['result']}</td><td>{'required' if c['required'] else 'informational'}</td></tr>"
        for c in summary["checks"]
    )
    form = f"<form method='post' action='/ui/pilots/{p.id}/acknowledge-source-policy'><textarea name='acknowledgement_text' required>I acknowledge the pilot source policy and will not resell raw data or send automated messages.</textarea><button>Acknowledge source policy</button></form>"
    guidance = {
        "operator_available": (
            "No active operator is configured.",
            "Create or activate an operator before marking this pilot ready.",
            "/ui/operators",
        ),
        "source_policy_acknowledged": (
            "The source policy has not been acknowledged for this pilot version.",
            "Acknowledge the matching policy version below.",
            f"/ui/pilots/{p.id}/readiness",
        ),
        "system_delivery_zero": (
            "System delivery count must remain zero.",
            "Investigate immediately if this check fails.",
            "/ui/reports/pilot",
        ),
    }
    guidance_rows = "".join(
        f"<li><strong>{esc(item['code'])}</strong>: {esc(guidance[item['code']][0])} Fix: {esc(guidance[item['code']][1])} <a href='{guidance[item['code']][2]}'>Open</a></li>"
        for item in summary["checks"]
        if item["result"] != "pass" and item["code"] in guidance
    )
    guidance_html = (
        f"<h2>Fix guidance</h2><ul>{guidance_rows}</ul>"
        if guidance_rows
        else "<p>All readiness checks have passed.</p>"
    )
    return page(
        "Pilot readiness",
        f"<p>Ready: <strong>{summary['ready']}</strong></p><table><tr><th>Check</th><th>Result</th><th>Class</th></tr>{rows}</table>{guidance_html}{form}",
    )


@router.post("/ui/pilots/{pilot_id}/acknowledge-source-policy")
def pilot_ack(
    pilot_id: uuid.UUID, acknowledgement_text: str = Form(...), db: Session = Depends(session)
) -> RedirectResponse:
    p = _pilot(db, pilot_id)
    db.add(
        PilotSourcePolicyAcknowledgement(
            pilot_id=p.id, policy_version=p.source_policy_version, acknowledgement_text=acknowledgement_text
        )
    )
    audit(db, p, "source_policy_acknowledged", None, after={"policy_version": p.source_policy_version})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}/readiness", status_code=303)


def _transition(p: PilotRun, target: str) -> None:
    allowed = {"draft": {"ready"}, "ready": {"active"}, "active": {"paused", "closed"}, "paused": {"active", "closed"}}
    if target not in allowed.get(p.status, set()):
        raise HTTPException(409, "invalid_pilot_transition")
    p.status = target
    p.updated_at = datetime.now(UTC)
    if target == "active":
        p.activated_at = datetime.now(UTC)
    if target == "closed":
        p.closed_at = datetime.now(UTC)


@router.post("/ui/pilots/{pilot_id}/mark-ready")
def pilot_mark_ready(pilot_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    p = _pilot(db, pilot_id)
    s = readiness_summary(db, p, settings)
    if not s["ready"]:
        raise HTTPException(409, "pilot_readiness_failed")
    _transition(p, "ready")
    audit(db, p, "marked_ready", None, after={"status": p.status})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}", status_code=303)


@router.post("/ui/pilots/{pilot_id}/activate")
def pilot_activate(pilot_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    p = _pilot(db, pilot_id)
    s = readiness_summary(db, p, settings)
    if not s["ready"]:
        raise HTTPException(409, "pilot_readiness_failed")
    _transition(p, "active")
    audit(db, p, "activated", None, after={"status": p.status})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}", status_code=303)


@router.post("/ui/pilots/{pilot_id}/pause")
def pilot_pause(pilot_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    p = _pilot(db, pilot_id)
    _transition(p, "paused")
    audit(db, p, "paused", None, after={"status": p.status})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}", status_code=303)


@router.post("/ui/pilots/{pilot_id}/close")
def pilot_close(pilot_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    p = _pilot(db, pilot_id)
    _transition(p, "closed")
    audit(db, p, "closed", None, after={"status": p.status})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}", status_code=303)


@router.get("/ui/pilots/{pilot_id}/exports", response_class=HTMLResponse)
def pilot_exports(pilot_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = _pilot(db, pilot_id)
    latest = db.scalar(
        select(PilotExportRun).where(PilotExportRun.pilot_id == p.id).order_by(PilotExportRun.created_at.desc())
    )
    body = f"<p>Last export: {esc(latest.created_at if latest else 'never')}</p><form method='post' action='/ui/pilots/{p.id}/exports/generate'><button>Generate export pack</button></form>"
    if latest:
        body += "<ul>" + "".join(f"<li>{esc(k)}: {esc(v)}</li>" for k, v in latest.files.items()) + "</ul>"
    return page("Pilot exports", body)


@router.post("/ui/pilots/{pilot_id}/exports/generate")
def pilot_export_generate(pilot_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    generate_export(db, _pilot(db, pilot_id), settings, None)
    return RedirectResponse(f"/ui/pilots/{pilot_id}/exports", status_code=303)


@router.get("/ui/pilots/{pilot_id}/retrospective", response_class=HTMLResponse)
def pilot_retrospective(pilot_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = _pilot(db, pilot_id)
    r = db.scalar(
        select(PilotRetrospective)
        .where(PilotRetrospective.pilot_id == p.id)
        .order_by(PilotRetrospective.updated_at.desc())
    )
    fields = (
        "what_worked",
        "what_failed",
        "false_positives",
        "false_negatives",
        "operator_friction",
        "demo_quality_issues",
        "source_quality_issues",
        "business_objections",
        "reply_quality",
        "meeting_quality",
        "next_sprint_recommendation",
    )
    form = (
        "<form method='post'>"
        + "".join(
            f"<label>{f.replace('_', ' ').title()}<textarea name='{f}'>{esc(getattr(r, f, '') if r else '')}</textarea></label>"
            for f in fields
        )
        + "<button>Save retrospective</button></form>"
    )
    return page("Pilot retrospective", form)


@router.post("/ui/pilots/{pilot_id}/retrospective")
def pilot_retrospective_save(
    pilot_id: uuid.UUID,
    what_worked: str = Form(""),
    what_failed: str = Form(""),
    false_positives: str = Form(""),
    false_negatives: str = Form(""),
    operator_friction: str = Form(""),
    demo_quality_issues: str = Form(""),
    source_quality_issues: str = Form(""),
    business_objections: str = Form(""),
    reply_quality: str = Form(""),
    meeting_quality: str = Form(""),
    next_sprint_recommendation: str = Form(""),
    db: Session = Depends(session),
) -> RedirectResponse:
    p = _pilot(db, pilot_id)
    r = db.scalar(
        select(PilotRetrospective)
        .where(PilotRetrospective.pilot_id == p.id)
        .order_by(PilotRetrospective.updated_at.desc())
    )
    values = locals()
    fields = (
        "what_worked",
        "what_failed",
        "false_positives",
        "false_negatives",
        "operator_friction",
        "demo_quality_issues",
        "source_quality_issues",
        "business_objections",
        "reply_quality",
        "meeting_quality",
        "next_sprint_recommendation",
    )
    if r is None:
        r = PilotRetrospective(pilot_id=p.id)
        db.add(r)
    for field in fields:
        setattr(r, field, values[field])
    r.updated_at = datetime.now(UTC)
    audit(db, p, "retrospective_saved", None, after={"pilot_id": str(p.id)})
    db.commit()
    return RedirectResponse(f"/ui/pilots/{p.id}/retrospective", status_code=303)


@router.get("/ui/businesses/{business_id}/proposal", response_class=HTMLResponse)
def proposal_for_business(business_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    proposals = db.scalars(
        select(ProposalPackage)
        .where(ProposalPackage.business_id == business_id)
        .order_by(ProposalPackage.created_at.desc())
    ).all()
    links = "".join(
        f'<li><a href="/ui/proposals/{p.id}">{html.escape(p.proposal_type)} — {html.escape(p.status)}</a></li>'
        for p in proposals
    )
    return HTMLResponse(
        f"<html><body><h1>Proposal packs: {html.escape(business.display_name)}</h1><p>This proposal pack is for operator review. LBOE does not send proposals, collect payments, create contracts, or provide legal advice.</p><ul>{links or '<li>No proposal packs yet.</li>'}</ul></body></html>"
    )


@router.get("/ui/proposals/{proposal_id}", response_class=HTMLResponse)
def proposal_detail(proposal_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = db.get(ProposalPackage, proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal_not_found")
    return HTMLResponse(
        f'<html><body><h1>{html.escape(p.proposal_type)}</h1><p>Status: {html.escape(p.status)}</p><p>{html.escape(p.summary)}</p><p><a href="/ui/proposals/{p.id}/review">Review</a> | <a href="/ui/proposals/{p.id}/export">Export</a></p></body></html>'
    )


@router.get("/ui/proposals/{proposal_id}/review", response_class=HTMLResponse)
def proposal_review_page(proposal_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = db.get(ProposalPackage, proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal_not_found")
    return HTMLResponse(
        f'<html><body><h1>Review proposal</h1><p>Status: {html.escape(p.status)}</p><form method="post"><input name="reviewer" value="operator"><textarea name="notes"></textarea><button name="decision" value="approve">Approve</button><button name="decision" value="request_changes">Request changes</button></form></body></html>'
    )


@router.post("/ui/proposals/{proposal_id}/review")
def proposal_review_submit(
    proposal_id: uuid.UUID, decision: str = Form(...), reviewer: str = Form(...), notes: str = Form("")
) -> RedirectResponse:
    from lboe_api.main import review_proposal

    with SessionLocal() as db:
        review_proposal(proposal_id, {"decision": decision, "reviewer": reviewer, "notes": notes}, db)
    return RedirectResponse(f"/ui/proposals/{proposal_id}", status_code=303)


@router.get("/ui/proposals/{proposal_id}/export", response_class=HTMLResponse)
def proposal_export_page(proposal_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    p = db.get(ProposalPackage, proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal_not_found")
    return HTMLResponse(
        f'<html><body><h1>Proposal export</h1><p>Status: {html.escape(p.status)}</p><form method="post"><button>Export locally</button></form></body></html>'
    )


@router.post("/ui/proposals/{proposal_id}/export")
def proposal_export_submit(proposal_id: uuid.UUID) -> RedirectResponse:
    from lboe_api.main import export_proposal

    with SessionLocal() as db:
        export_proposal(proposal_id, db)
    return RedirectResponse(f"/ui/proposals/{proposal_id}", status_code=303)


@router.get("/ui/queues/proposal-ready", response_class=HTMLResponse)
def proposal_ready_queue(db: Session = Depends(session)) -> HTMLResponse:
    proposals = db.scalars(
        select(ProposalPackage)
        .where(ProposalPackage.status.in_(["draft", "changes_requested"]))
        .order_by(ProposalPackage.created_at)
    ).all()
    rows = "".join(
        f'<li><a href="/ui/proposals/{p.id}">{html.escape(str(p.business_id))}</a> — {html.escape(p.status)}</li>'
        for p in proposals
    )
    return HTMLResponse(
        f"<html><body><h1>Proposal-ready queue</h1><ul>{rows or '<li>Queue empty.</li>'}</ul></body></html>"
    )


@router.get("/ui/businesses/{business_id}/delivery", response_class=HTMLResponse)
def delivery_for_business(business_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="business_not_found")
    projects = db.scalars(
        select(DeliveryProject)
        .where(DeliveryProject.business_id == business_id)
        .order_by(DeliveryProject.created_at.desc())
    ).all()
    rows = "".join(
        f'<li><a href="/ui/delivery-projects/{p.id}">{html.escape(p.title)}</a> — {html.escape(p.status)}</li>'
        for p in projects
    )
    return HTMLResponse(
        f"<html><body><h1>Delivery: {html.escape(business.display_name)}</h1><p>LBOE does not store credentials. Use an approved password manager. Approval records are operator assertions, not e-signatures.</p><ul>{rows or '<li>No delivery projects.</li>'}</ul></body></html>"
    )


@router.get("/ui/delivery-projects/{project_id}", response_class=HTMLResponse)
def delivery_detail(project_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    project = db.get(DeliveryProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="delivery_project_not_found")
    items = db.scalars(
        select(DeliveryChecklistItem).where(DeliveryChecklistItem.delivery_project_id == project.id)
    ).all()
    milestones = db.scalars(select(DeliveryMilestone).where(DeliveryMilestone.delivery_project_id == project.id)).all()
    checks = "".join(
        f"<li>{html.escape(i.category)} / {html.escape(i.code)}: {html.escape(i.status)}</li>" for i in items
    )
    marks = "".join(f"<li>{html.escape(m.milestone_type)}: {html.escape(m.status)}</li>" for m in milestones)
    return HTMLResponse(
        f"<html><body><h1>{html.escape(project.title)}</h1><p>Status: {html.escape(project.status)}</p><p>Safety: no credentials, payments, contracts, or automated deployment are stored here.</p><h2>Checklist</h2><ul>{checks}</ul><h2>Milestones</h2><ul>{marks}</ul></body></html>"
    )


@router.get("/ui/queues/delivery", response_class=HTMLResponse)
def delivery_queue(db: Session = Depends(session)) -> HTMLResponse:
    projects = db.scalars(
        select(DeliveryProject)
        .where(DeliveryProject.status.not_in(["closed", "cancelled", "delivered"]))
        .order_by(DeliveryProject.created_at)
    ).all()
    rows = "".join(
        f'<li><a href="/ui/delivery-projects/{p.id}">{html.escape(p.title)}</a> — {html.escape(p.status)}</li>'
        for p in projects
    )
    return HTMLResponse(f"<html><body><h1>Delivery queue</h1><ul>{rows or '<li>Queue empty.</li>'}</ul></body></html>")


@router.get("/ui/system", response_class=HTMLResponse)
def system_page(db: Session = Depends(session)) -> HTMLResponse:
    from lboe_api.main import system_status

    status = system_status(db)
    storage = status["storage"]
    auth = status["auth"]
    safety = status["safety"]
    body = (
        f"<section><h2>Connectivity</h2><p>Database: <span class='badge'>{esc(status['database'])}</span> · Migration: {esc(status['migration']['current'] or 'unknown')} / expected {esc(status['migration']['expected'])}</p></section>"
        f"<section><h2>Configuration</h2><p>Environment: {esc(status['environment'])}<br>Storage backend: {esc(storage['backend'])}<br>Artifact root writable: {esc(storage['artifact_root_writable'])}<br>Export root writable: {esc(storage['export_root_writable'])}<br>Auth enabled: {esc(auth['enabled'])}<br>Secure cookies: {esc(auth['secure_cookies'])}</p></section>"
        f"<section><h2>Operations</h2><p>Failed/not-eligible jobs: {status['failed_or_not_eligible_jobs']}<br>Preview links: {status['preview_link_count']}<br>System delivery count: <strong>{status['system_delivery_count']}</strong></p></section>"
        f"<section><h2>Safety</h2><p>Sending: {esc(safety['sending_enabled'])}<br>Inbox sync: {esc(safety['inbox_sync_enabled'])}<br>CRM sync: {esc(safety['crm_sync_enabled'])}<br>Credentials stored: {esc(safety['credentials_stored'])}</p></section>"
    )
    return page("System status", body)


@router.post("/ui/businesses/{business_id}/delivery")
def create_delivery_from_ui(
    business_id: uuid.UUID, title: str = Form("Delivery project"), db: Session = Depends(session)
) -> RedirectResponse:
    from lboe_api.main import create_delivery_project

    result = create_delivery_project(business_id, {"title": title, "operator_created": True}, db)
    return RedirectResponse(
        f"/ui/delivery-projects/{result['id']}" if result.get("id") else f"/ui/businesses/{business_id}/delivery",
        status_code=303,
    )


@router.post("/ui/delivery-projects/{project_id}/checklist")
def update_delivery_checklist_ui(
    project_id: uuid.UUID,
    category: str = Form(...),
    code: str = Form(...),
    status: str = Form("verified"),
    notes: str = Form(""),
    db: Session = Depends(session),
) -> RedirectResponse:
    from lboe_api.main import update_delivery_checklist

    update_delivery_checklist(project_id, {"category": category, "code": code, "status": status, "notes": notes}, db)
    return RedirectResponse(f"/ui/delivery-projects/{project_id}", status_code=303)


@router.post("/ui/delivery-projects/{project_id}/milestone")
def add_delivery_milestone_ui(
    project_id: uuid.UUID, milestone_type: str = Form(...), note: str = Form(""), db: Session = Depends(session)
) -> RedirectResponse:
    from lboe_api.main import add_delivery_milestone

    add_delivery_milestone(project_id, {"milestone_type": milestone_type, "status": "complete", "note": note}, db)
    return RedirectResponse(f"/ui/delivery-projects/{project_id}", status_code=303)


@router.post("/ui/delivery-projects/{project_id}/approval")
def add_delivery_approval_ui(
    project_id: uuid.UUID,
    approved_item: str = Form(...),
    client_assertion: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(session),
) -> RedirectResponse:
    from lboe_api.main import add_delivery_approval

    add_delivery_approval(
        project_id,
        {
            "approval_type": "client_approval",
            "approved_item": approved_item,
            "client_assertion": client_assertion,
            "notes": notes,
        },
        db,
    )
    return RedirectResponse(f"/ui/delivery-projects/{project_id}", status_code=303)


@router.post("/ui/delivery-projects/{project_id}/export")
def export_delivery_ui(project_id: uuid.UUID, db: Session = Depends(session)) -> RedirectResponse:
    from lboe_api.main import export_delivery_project

    export_delivery_project(project_id, db)
    return RedirectResponse(f"/ui/delivery-projects/{project_id}", status_code=303)
