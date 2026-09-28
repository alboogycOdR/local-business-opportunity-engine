# ruff: noqa: E501
from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from lboe_api.db import (
    AuditArtifact,
    AuditRun,
    Business,
    BusinessBrief,
    Campaign,
    DemoArtifact,
    DemoPreviewAccessEvent,
    DemoPreviewLink,
    DemoQaRun,
    EnrichmentFactRow,
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
    SuppressionEntry,
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
        f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)} · LBOE</title><link rel='stylesheet' href='/ui/static/ui.css'></head><body><header><a href='/ui'><strong>LBOE Operator Cockpit</strong></a><nav><a href='/ui/campaigns'>Campaigns</a><a href='/ui/pilots'>Pilots</a><a href='/ui/queues'>Queues</a><a href='/ui/reports/pilot'>Reports</a><a href='/ui/operators'>Operators</a></nav></header><div class='safety'>System delivery is disabled. LBOE does not send email, WhatsApp, SMS, or CRM messages.</div><main><h1>{esc(title)}</h1>{body}</main></body></html>"""
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


@router.get("/ui", response_class=HTMLResponse)
def dashboard(db: Session = Depends(session)) -> HTMLResponse:
    report = build_pilot_report(db)
    quality = {item["code"]: item["count"] for item in report["quality_metrics"]}
    body = (
        metric_cards(report)
        + f"<p class='notice'>System delivery count: <strong>{quality.get('system_delivery_count', 0)}</strong></p><p><a class='button' href='/ui/campaigns'>Open campaigns</a> <a class='button' href='/ui/queues'>Open queues</a></p>"
    )
    return page("Pilot dashboard", body)


@router.get("/ui/campaigns", response_class=HTMLResponse)
def campaigns(db: Session = Depends(session)) -> HTMLResponse:
    rows = []
    for campaign in db.scalars(
        select(__import__("lboe_api.db", fromlist=["Campaign"]).Campaign).order_by(
            __import__("lboe_api.db", fromlist=["Campaign"]).Campaign.created_at.desc()
        )
    ).all():
        count = (
            db.scalar(select(Business).where(Business.campaign_id == campaign.id).count())
            if False
            else len(db.scalars(select(Business).where(Business.campaign_id == campaign.id)).all())
        )
        rows.append(
            f"<tr><td><a href='/ui/campaigns/{campaign.id}'>{esc(campaign.name)}</a></td><td>{esc(campaign.vertical)}</td><td>{esc(campaign.geography)}</td><td>{count}</td><td>{esc(campaign.created_at)}</td></tr>"
        )
    table = (
        "<table><tr><th>Campaign</th><th>Vertical</th><th>Geography</th><th>Businesses</th><th>Created</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    form = "<h2>Create campaign</h2><form method='post' action='/ui/campaigns'><input name='name' placeholder='Campaign name' required><input name='vertical' placeholder='Vertical' required><input name='geography' placeholder='Geography'><button>Create</button></form>"
    return page("Campaigns", table + form)


@router.post("/ui/campaigns")
def create_campaign(
    name: str = Form(...), vertical: str = Form(...), geography: str = Form(""), db: Session = Depends(session)
) -> RedirectResponse:
    from lboe_api.db import Campaign

    campaign = Campaign(name=name, vertical=vertical, geography=geography or None)
    db.add(campaign)
    db.commit()
    return RedirectResponse(f"/ui/campaigns/{campaign.id}", status_code=303)


@router.get("/ui/campaigns/{campaign_id}", response_class=HTMLResponse)
def campaign_detail(
    campaign_id: uuid.UUID,
    state: str | None = None,
    action: str | None = None,
    band: str | None = None,
    q: str | None = None,
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
        if (
            state
            and business.state != state
            or q
            and q.lower() not in business.display_name.lower()
            or action
            and (not brief or brief.recommended_next_action != action)
            or band
            and (not score or score.band != band)
        ):
            continue
        demo = db.scalar(
            select(GeneratedDemo)
            .where(GeneratedDemo.business_id == business.id)
            .order_by(GeneratedDemo.created_at.desc())
        )
        rows.append(
            f"<tr><td><a href='/ui/businesses/{business.id}'>{esc(business.display_name)}</a></td><td>{esc(business.category)}</td><td>{esc(business.locality)}</td><td><span class='badge'>{esc(business.state)}</span></td><td>{score.score if score else '—'}</td><td>{esc(score.band if score else '')}</td><td>{esc(brief.recommended_next_action if brief else '')}</td><td>{esc(demo.status if demo else '')}</td></tr>"
        )
    filters = f"<form method='get'><input name='q' value='{esc(q)}' placeholder='Search business'><input name='state' value='{esc(state)}' placeholder='State'><input name='action' value='{esc(action)}' placeholder='Recommended action'><input name='band' value='{esc(band)}' placeholder='Score band'><button>Filter</button></form>"
    table = (
        "<table><tr><th>Business</th><th>Category</th><th>Locality</th><th>State</th><th>Score</th><th>Band</th><th>Action</th><th>Demo</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return page(
        f"Campaign · {campaign.name}", f"<p>{esc(campaign.vertical)} · {esc(campaign.geography)}</p>{filters}{table}"
    )


@router.get("/ui/businesses/{business_id}", response_class=HTMLResponse)
def business_detail(business_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
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
    component_html = (
        "".join(
            f"<li>{esc(c.code)} · {c.points}/{c.max_points} points · confidence {c.confidence} · source {esc(c.source_type)} · evidence {len(c.evidence) if isinstance(c.evidence, (list, dict)) else 1}</li>"
            for c in score_components
        )
        or "<li>None</li>"
    )
    hold_html = "".join(f"<li>{esc(h.code)} · {esc(h.reason)}</li>" for h in score_holds) or "<li>None</li>"
    observability = f"<section><h2>Score observability</h2><p>Score: {score.score if score else '—'} · Band: {esc(score.band if score else '')} · Action: {esc(score.recommended_next_action if score else '')} · Latest audit: {esc(latest_audit.id if latest_audit else '—')} · Brief: {esc(brief.id if brief else '—')}</p><h3>Components</h3><ul>{component_html}</ul><h3>Holds</h3><ul>{hold_html}</ul></section>"
    pilot_banner = ""
    if pilot is not None:
        pilot_banner = f"<div class='safety'>{'DRY RUN MODE — manual outreach and CRM outcome logging are blocked by the operator console.' if pilot.mode == 'dry_run' else 'ACTIVE PILOT MODE — manual records represent operator activity; LBOE still sends nothing.'} <a href='/ui/pilots/{pilot.id}'>View pilot</a></div>"
    body = (
        pilot_banner
        + observability
        + f"<p class='badge'>{esc(business.state)}</p><section><h2>Identity</h2><p>{esc(business.display_name)} · {esc(business.category)} · {esc(business.locality)}<br>{esc(business.address_text)}</p></section><section><h2>Score / brief</h2><p>Score: {score.score if score else '—'} ({esc(score.band if score else '')})<br>Recommended action: {esc(brief.recommended_next_action if brief else '—')}</p></section><section><h2>Enrichment evidence</h2><ul>{''.join(f'<li>{esc(run.status)} · {esc(run.adapter_version)} · {len(db.scalars(select(EnrichmentFactRow).where(EnrichmentFactRow.enrichment_run_id == run.id)).all())} facts</li>' for run in enrichment_runs) or '<li>No enrichment run</li>'}</ul></section><section><h2>Demo / outreach</h2><p>{esc(package.status if package else 'No outreach draft')}</p><ul>{demo_html}</ul></section><section><h2>CRM events</h2><ul>{event_html}</ul></section><section><h2>Assignments</h2><ul>{''.join(f'<li>{a.operator_id} · {a.status}</li>' for a in assignments) or '<li>None</li>'}</ul><form method='post' action='/ui/businesses/{business_id}/assign'><select name='operator_id'>{operator_options}</select><button>Assign</button></form></section><section><h2>Operator notes</h2><ul>{comment_html}</ul><form method='post' action='/ui/businesses/{business_id}/comment'><textarea name='body' required placeholder='Append an operator note'></textarea><button>Add note</button></form></section><section><h2>Safe actions</h2><p>All workflow actions remain subject to backend lifecycle and suppression gates.</p><form method='post' action='/ui/businesses/{business_id}/suppress'><input name='reason' required placeholder='Suppression reason'><button>Suppress business</button></form></section>"
    )
    return page(business.display_name, body)


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
    if queue_name == "no-demo-reason":
        return no_demo_reason_queue(db)
    if queue_name == "qa-failed":
        return qa_failed_queue(db)
    if queue_name == "not-outreach-ready":
        return not_outreach_ready_queue(db)
    if queue_name == "weak-evidence":
        return weak_evidence_queue(db)
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
    }
    if queue_name not in mapping:
        raise HTTPException(404, "queue_not_found")
    title, query = mapping[queue_name]
    items = db.scalars(query).all()  # type: ignore[call-overload]
    rows = []
    for item in items:
        business_id = item.business_id
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
