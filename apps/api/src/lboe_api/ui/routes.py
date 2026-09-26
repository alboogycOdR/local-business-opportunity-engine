# ruff: noqa: E501
from __future__ import annotations

import hashlib
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
    Business,
    BusinessBrief,
    DemoArtifact,
    DemoPreviewAccessEvent,
    DemoPreviewLink,
    GeneratedDemo,
    LeadCrmEvent,
    Operator,
    OperatorAssignment,
    OperatorAuditEvent,
    OperatorComment,
    OpportunityScore,
    OutreachDraftPackage,
    SuppressionEntry,
)
from lboe_api.main import SessionLocal, settings
from lboe_api.reporting_service import build_pilot_report

router = APIRouter()
DISCLAIMER = "Concept preview prepared independently for demonstration. Not the official website of this business."


def session() -> Session:
    return SessionLocal()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)} · LBOE</title><link rel='stylesheet' href='/ui/static/ui.css'></head><body><header><a href='/ui'><strong>LBOE Operator Cockpit</strong></a><nav><a href='/ui/campaigns'>Campaigns</a><a href='/ui/queues'>Queues</a><a href='/ui/reports/pilot'>Reports</a><a href='/ui/operators'>Operators</a></nav></header><div class='safety'>System delivery is disabled. LBOE does not send email, WhatsApp, SMS, or CRM messages.</div><main><h1>{esc(title)}</h1>{body}</main></body></html>"""
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
            f"<li><a href='/ui/demos/{demo.id}/preview'>Demo {demo.id}</a> — {esc(demo.status)} <a href='/ui/demos/{demo.id}/preview-links'>preview links</a></li>"
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
    body = f"<p class='badge'>{esc(business.state)}</p><section><h2>Identity</h2><p>{esc(business.display_name)} · {esc(business.category)} · {esc(business.locality)}<br>{esc(business.address_text)}</p></section><section><h2>Score / brief</h2><p>Score: {score.score if score else '—'} ({esc(score.band if score else '')})<br>Recommended action: {esc(brief.recommended_next_action if brief else '—')}</p></section><section><h2>Demo / outreach</h2><p>{esc(package.status if package else 'No outreach draft')}</p><ul>{demo_html}</ul></section><section><h2>CRM events</h2><ul>{event_html}</ul></section><section><h2>Assignments</h2><ul>{''.join(f'<li>{a.operator_id} · {a.status}</li>' for a in assignments) or '<li>None</li>'}</ul><form method='post' action='/ui/businesses/{business_id}/assign'><select name='operator_id'>{operator_options}</select><button>Assign</button></form></section><section><h2>Operator notes</h2><ul>{comment_html}</ul><form method='post' action='/ui/businesses/{business_id}/comment'><textarea name='body' required placeholder='Append an operator note'></textarea><button>Add note</button></form></section><section><h2>Safe actions</h2><p>All workflow actions remain subject to backend lifecycle and suppression gates.</p><form method='post' action='/ui/businesses/{business_id}/suppress'><input name='reason' required placeholder='Suppression reason'><button>Suppress business</button></form></section>"
    return page(business.display_name, body)


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


@router.get("/ui/demos/{demo_id}/preview-links", response_class=HTMLResponse)
def preview_links(demo_id: uuid.UUID, db: Session = Depends(session)) -> HTMLResponse:
    links = db.scalars(
        select(DemoPreviewLink).where(DemoPreviewLink.demo_id == demo_id).order_by(DemoPreviewLink.created_at.desc())
    ).all()
    rows = (
        "".join(
            f"<li>{esc(link.label)} · {esc(link.status)} · expires {esc(link.expires_at)} "
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
    if link.status != "active" or (link.expires_at and link.expires_at < now):
        if link.status == "active" and link.expires_at and link.expires_at < now:
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
