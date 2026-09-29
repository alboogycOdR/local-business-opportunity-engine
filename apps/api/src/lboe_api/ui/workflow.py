# ruff: noqa: E501
"""Operator-console forms for the human-gated pipeline steps.

Before this module the review, draft, consent, contact-log, CRM and follow-up
steps existed only as JSON endpoints, so an operator using /ui stalled at
``REVIEW_PENDING``.  Every form posts to a thin UI route that calls the same
API function (and therefore the same gates), then redirects back with a
readable outcome.  Nothing here sends a message.
"""

from __future__ import annotations

import html
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from lboe_domain import (
    DemoReviewRequest,
    LeadResponseLogRequest,
    LeadState,
    ManualOutreachLogRequest,
    OutreachReadinessRequest,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from lboe_api.db import (
    Business,
    GeneratedDemo,
    Operator,
    OutreachDraftMessage,
    OutreachDraftPackage,
    OutreachExecutionRecord,
)
from lboe_api.pilot_service import pilot_for_business
from lboe_api.ui.presentation import friendly, local_input_value, parse_local_datetime, status_label
from lboe_api.ui.routes import session

router = APIRouter()

REVIEWABLE_DEMO_STATUSES = {"qa_passed", "review_pending", "changes_requested", "manual_edit_required"}
CONSENT_BASIS_OPTIONS = (
    ("", "Choose the basis you are relying on…"),
    ("explicit_permission_recorded", "Explicit permission recorded (they asked to be contacted)"),
    ("existing_relationship", "Existing relationship with this business"),
    ("public_business_contact_for_manual_outreach", "Public business contact — one manual, opt-out-friendly message"),
)
CHANNEL_LABELS = {"email": "Email", "whatsapp": "WhatsApp", "phone_script": "Phone call", "manual_note": "Other"}
CRM_EVENTS_BY_STATE = {
    LeadState.CONTACTED.value: (
        ("reply_received", "They replied"),
        ("no_response_note", "No response yet"),
        ("lost", "Not interested / lost"),
    ),
    LeadState.REPLIED.value: (("meeting_scheduled", "Meeting scheduled"), ("lost", "Not interested / lost")),
    LeadState.MEETING.value: (("proposal_sent", "Proposal sent"), ("lost", "Not interested / lost")),
    LeadState.PROPOSAL.value: (("won", "Won"), ("lost", "Lost")),
}


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _field(label: str, control: str, hint: str = "") -> str:
    hint_html = f"<small class='hint'>{_e(hint)}</small>" if hint else ""
    return f"<label class='field'><span>{_e(label)}</span>{control}{hint_html}</label>"


def current_operator_name(request: Request, db: Session) -> str:
    operator_id = request.cookies.get("lboe_operator_id")
    operator = None
    if operator_id:
        try:
            operator = db.get(Operator, uuid.UUID(operator_id))
        except ValueError:
            operator = None
    if operator is None:
        operator = db.scalar(select(Operator).where(Operator.active.is_(True)).order_by(Operator.created_at))
    return operator.display_name if operator else ""


def _redirect(business_id: uuid.UUID, *, done: str | None = None, error: str | None = None) -> RedirectResponse:
    query = f"action_completed={quote_plus(done)}" if done else f"action_error={quote_plus(error or 'failed')}"
    return RedirectResponse(f"/ui/businesses/{business_id}?{query}#workflow", status_code=303)


def _outcome(business_id: uuid.UUID, result: dict[str, Any], done: str) -> RedirectResponse:
    status = str(result.get("status", ""))
    if status.startswith("not_"):
        return _redirect(business_id, error=friendly({"reason": result.get("reason")}))
    return _redirect(business_id, done=done)


def workflow_panel(request: Request, db: Session, business: Business, suppressed: bool) -> str:
    """The human-gated step(s) that apply to this business right now."""
    if suppressed:
        return ""
    reviewer = _e(current_operator_name(request, db))
    sections: list[str] = []
    pilot = pilot_for_business(db, business.id)
    dry_run = pilot is not None and pilot.mode == "dry_run"
    demo = db.scalar(
        select(GeneratedDemo).where(GeneratedDemo.business_id == business.id).order_by(GeneratedDemo.created_at.desc())
    )
    if (
        demo is not None
        and demo.status in REVIEWABLE_DEMO_STATUSES
        and business.state == LeadState.REVIEW_PENDING.value
    ):
        from lboe_api.main import REVIEW_CHECKLIST

        checks = "".join(
            f"<label class='check'><input type='checkbox' name='checklist' value='{_e(code)}'> {_e(label)}</label>"
            for code, label in REVIEW_CHECKLIST
        )
        sections.append(
            f"<form method='post' action='/ui/demos/{demo.id}/review' class='workflow-step'>"
            f"<h3>Review the concept preview</h3><p>Open the <a href='/ui/demos/{demo.id}/preview'>concept preview</a> "
            f"({_e(status_label(demo.status))}) and confirm every item before approving. Approval does not contact anyone.</p>"
            f"<fieldset><legend>Review checklist</legend>{checks}</fieldset>"
            + _field("Reviewer", f"<input name='reviewer' required value='{reviewer}' autocomplete='name'>")
            + _field("Notes", "<textarea name='notes' rows='2'></textarea>")
            + "<fieldset><legend>Decision</legend>"
            "<label class='check'><input type='radio' name='decision' value='approve' required> Approve concept</label>"
            "<label class='check'><input type='radio' name='decision' value='request_changes'> Request changes</label>"
            "<label class='check'><input type='radio' name='decision' value='request_regeneration'> Regenerate</label>"
            "<label class='check'><input type='radio' name='decision' value='reject'> Reject</label></fieldset>"
            "<button class='button-primary'>Record review decision</button></form>"
        )
    package = db.scalar(
        select(OutreachDraftPackage)
        .where(OutreachDraftPackage.business_id == business.id)
        .order_by(OutreachDraftPackage.created_at.desc())
    )
    if business.state == LeadState.APPROVED_FOR_OUTREACH.value and (package is None or package.status != "ready"):
        boxes = "".join(
            f"<label class='check'><input type='checkbox' name='channels' value='{code}' {'checked' if code == 'email' else ''}> {label}</label>"
            for code, label in CHANNEL_LABELS.items()
        )
        sections.append(
            f"<form method='post' action='/ui/businesses/{business.id}/outreach-draft' class='workflow-step'>"
            "<h3>Draft outreach (copy only)</h3><p>LBOE prepares text for you to review. It never sends it.</p>"
            f"<fieldset><legend>Channels to draft</legend>{boxes}</fieldset>"
            "<button class='button-primary'>Prepare drafts</button></form>"
        )
    if business.state == LeadState.APPROVED_FOR_OUTREACH.value and package is not None and package.status == "ready":
        sections.append(
            f"<form method='post' action='/ui/businesses/{business.id}/outreach-readiness' class='workflow-step'>"
            "<h3>Start the consent decision</h3><p>Drafts are ready. Next, decide whether you may contact this business.</p>"
            f"<input type='hidden' name='outreach_draft_package_id' value='{package.id}'>"
            "<input type='hidden' name='decision' value='prepare_consent_review'>"
            + _field("Reviewer", f"<input name='reviewer' required value='{reviewer}' autocomplete='name'>")
            + "<button class='button-primary'>Open consent decision</button></form>"
        )
    if business.state == LeadState.CONSENT_PENDING.value and package is not None:
        messages = db.scalars(select(OutreachDraftMessage).where(OutreachDraftMessage.package_id == package.id)).all()
        boxes = "".join(
            f"<label class='check'><input type='checkbox' name='selected_channels' value='{_e(m.channel)}'> {_e(CHANNEL_LABELS.get(m.channel, m.channel))}</label>"
            for m in messages
        )
        options = "".join(f"<option value='{code}'>{_e(label)}</option>" for code, label in CONSENT_BASIS_OPTIONS)
        sections.append(
            f"<form method='post' action='/ui/businesses/{business.id}/outreach-readiness' class='workflow-step'>"
            "<h3>Consent decision</h3><p class='warning'>Finding a phone number or email on a listing is <strong>not</strong> consent. "
            "Approve only if you can state the basis below; this clears <em>one manual</em> contact and sends nothing.</p>"
            f"<input type='hidden' name='outreach_draft_package_id' value='{package.id}'>"
            + _field("Basis for contact", f"<select name='consent_basis_type' required>{options}</select>")
            + _field(
                "Evidence for that basis",
                "<textarea name='consent_basis_notes' rows='2' required></textarea>",
                "e.g. where and when permission was given",
            )
            + f"<fieldset><legend>Channels you will use</legend>{boxes}</fieldset>"
            + _field("Reviewer", f"<input name='reviewer' required value='{reviewer}' autocomplete='name'>")
            + "<fieldset><legend>Decision</legend>"
            "<label class='check'><input type='radio' name='decision' value='approve_for_manual_outreach' required> Clear for one manual contact</label>"
            "<label class='check'><input type='radio' name='decision' value='reject_outreach'> Do not contact now</label>"
            "<label class='check'><input type='radio' name='decision' value='suppress_business'> Suppress permanently</label></fieldset>"
            "<button class='button-primary'>Record consent decision</button></form>"
        )
    if business.state == LeadState.OUTREACH_READY.value and package is not None and not dry_run:
        messages = db.scalars(
            select(OutreachDraftMessage).where(
                OutreachDraftMessage.package_id == package.id, OutreachDraftMessage.approved.is_(True)
            )
        ).all()
        options = "".join(
            f"<option value='{m.id}'>{_e(CHANNEL_LABELS.get(m.channel, m.channel))} draft</option>" for m in messages
        )
        sections.append(
            f"<form method='post' action='/ui/businesses/{business.id}/outreach-log' class='workflow-step'>"
            "<h3>Record the contact you made</h3><p>Only record this <strong>after</strong> you contacted them yourself. "
            f"<a href='/ui/businesses/{business.id}/outreach-workbench'>Copy the approved draft</a>.</p>"
            f"<input type='hidden' name='outreach_draft_package_id' value='{package.id}'>"
            + _field("Message used", f"<select name='outreach_draft_message_id' required>{options}</select>")
            + _field(
                "When you sent it",
                f"<input type='datetime-local' name='sent_at' required value='{local_input_value(datetime.now(UTC))}'>",
            )
            + _field("Your name", f"<input name='operator' required value='{reviewer}' autocomplete='name'>")
            + _field("Notes", "<textarea name='notes' rows='2'></textarea>")
            + "<button class='button-primary'>Record manual contact</button></form>"
        )
    events = None if dry_run else CRM_EVENTS_BY_STATE.get(business.state)
    if events:
        radios = "".join(
            f"<label class='check'><input type='radio' name='event_type' value='{code}' required> {_e(label)}</label>"
            for code, label in events
        )
        channel_options = "".join(
            f"<option value='{code}'>{label}</option>"
            for code, label in (
                ("email", "Email"),
                ("whatsapp", "WhatsApp"),
                ("phone", "Phone"),
                ("in_person", "In person"),
            )
        )
        sections.append(
            f"<form method='post' action='/ui/businesses/{business.id}/crm-event' class='workflow-step'>"
            f"<h3>Record what happened</h3><fieldset><legend>Outcome</legend>{radios}</fieldset>"
            + _field("Channel", f"<select name='channel'>{channel_options}</select>")
            + _field("Summary", "<textarea name='summary' rows='2' required></textarea>")
            + _field(
                "When",
                f"<input type='datetime-local' name='occurred_at' required value='{local_input_value(datetime.now(UTC))}'>",
            )
            + _field("Your name", f"<input name='operator' required value='{reviewer}' autocomplete='name'>")
            + "<button class='button-primary'>Record outcome</button></form>"
        )
    if not dry_run:
        sections.append(
            f"<form method='post' action='/ui/businesses/{business.id}/follow-ups' class='workflow-step'>"
            "<h3>Schedule a follow-up reminder</h3><p>A to-do for you in the follow-up queue. LBOE sends no reminders.</p>"
            + _field("What to do", "<input name='reason' required maxlength='500'>")
            + _field("Due", "<input type='datetime-local' name='due_at' required>")
            + "<button class='button-secondary'>Add follow-up</button></form>"
        )
    else:
        sections.append(
            "<div class='notice' role='status'>Dry run mode records no real manual contact or CRM outcomes. "
            "Switch the pilot to active mode before recording real operator activity.</div>"
        )
    return (
        "<section class='section' id='workflow'><h2>Next human decision</h2>"
        "<p class='muted'>Each step records who decided and why. Nothing is sent by LBOE.</p>"
        + "".join(sections)
        + "</section>"
    )


def _exists(db: Session, business_id: uuid.UUID) -> None:
    if db.get(Business, business_id) is None:
        raise HTTPException(404, "business_not_found")


@router.post("/ui/demos/{demo_id}/review")
async def review_demo_ui(demo_id: uuid.UUID, request: Request, db: Session = Depends(session)) -> RedirectResponse:
    from lboe_api.main import REVIEW_CHECKLIST, review_demo

    demo = db.get(GeneratedDemo, demo_id)
    if demo is None:
        raise HTTPException(404, "demo_not_found")
    form = await request.form()
    confirmed = set(form.getlist("checklist"))
    payload = {
        "decision": form.get("decision"),
        "reviewer": form.get("reviewer"),
        "notes": form.get("notes") or "",
        "checklist": [{"code": code, "label": label, "passed": code in confirmed} for code, label in REVIEW_CHECKLIST],
    }
    try:
        review_demo(demo_id, DemoReviewRequest.model_validate(payload), db)
    except ValidationError as exc:
        return _redirect(demo.business_id, error=friendly(exc.errors()))
    except HTTPException as exc:
        return _redirect(demo.business_id, error=friendly(exc.detail))
    return _redirect(demo.business_id, done=f"concept review recorded ({payload['decision']})")


@router.post("/ui/businesses/{business_id}/outreach-draft")
async def outreach_draft_ui(
    business_id: uuid.UUID, request: Request, db: Session = Depends(session)
) -> RedirectResponse:
    from lboe_api.main import create_outreach_draft

    _exists(db, business_id)
    form = await request.form()
    channels = list(form.getlist("channels"))
    if not channels:
        return _redirect(business_id, error="Choose at least one channel to draft.")
    result = create_outreach_draft(business_id, {"channels": channels, "idempotency_key": f"ui-{uuid.uuid4()}"}, db)
    return _outcome(business_id, result, "outreach drafts prepared")


@router.post("/ui/businesses/{business_id}/outreach-readiness")
async def outreach_readiness_ui(
    business_id: uuid.UUID, request: Request, db: Session = Depends(session)
) -> RedirectResponse:
    from lboe_api.main import create_outreach_readiness

    _exists(db, business_id)
    form = await request.form()
    payload = {
        "outreach_draft_package_id": form.get("outreach_draft_package_id"),
        "decision": form.get("decision"),
        "reviewer": form.get("reviewer"),
        "selected_channels": list(form.getlist("selected_channels")),
        "consent_basis_type": form.get("consent_basis_type") or "unknown",
        "consent_basis_notes": form.get("consent_basis_notes") or "",
        "notes": form.get("notes") or "",
        "idempotency_key": f"ui-{uuid.uuid4()}",
    }
    try:
        result = create_outreach_readiness(business_id, OutreachReadinessRequest.model_validate(payload), db)
    except ValidationError as exc:
        return _redirect(business_id, error=friendly(exc.errors()))
    except HTTPException as exc:
        return _redirect(business_id, error=friendly(exc.detail))
    return _outcome(business_id, result, "consent decision recorded")


@router.post("/ui/businesses/{business_id}/outreach-log")
async def outreach_log_ui(business_id: uuid.UUID, request: Request, db: Session = Depends(session)) -> RedirectResponse:
    from lboe_api.main import create_outreach_log

    _exists(db, business_id)
    form = await request.form()
    message = db.get(OutreachDraftMessage, uuid.UUID(str(form.get("outreach_draft_message_id"))))
    if message is None:
        return _redirect(business_id, error="Choose the approved message you used.")
    try:
        payload = ManualOutreachLogRequest(
            outreach_draft_package_id=uuid.UUID(str(form.get("outreach_draft_package_id"))),
            outreach_draft_message_id=message.id,
            channel=message.channel,  # type: ignore[arg-type]
            operator=str(form.get("operator") or ""),
            sent_at=parse_local_datetime(str(form.get("sent_at"))),
            notes=str(form.get("notes") or ""),
            idempotency_key=f"ui-{uuid.uuid4()}",
        )
        result = create_outreach_log(business_id, payload, db)
    except (ValidationError, ValueError) as exc:
        return _redirect(business_id, error=friendly(exc.errors() if isinstance(exc, ValidationError) else str(exc)))
    return _outcome(business_id, result, "manual contact recorded")


@router.post("/ui/businesses/{business_id}/crm-event")
async def crm_event_ui(business_id: uuid.UUID, request: Request, db: Session = Depends(session)) -> RedirectResponse:
    from lboe_api.main import create_crm_event

    _exists(db, business_id)
    form = await request.form()
    execution = db.scalar(
        select(OutreachExecutionRecord)
        .where(OutreachExecutionRecord.business_id == business_id)
        .order_by(OutreachExecutionRecord.created_at.desc())
    )
    try:
        payload = LeadResponseLogRequest(
            outreach_execution_record_id=execution.id if execution else None,
            event_type=str(form.get("event_type")),  # type: ignore[arg-type]
            channel=str(form.get("channel") or "email"),  # type: ignore[arg-type]
            operator=str(form.get("operator") or ""),
            occurred_at=parse_local_datetime(str(form.get("occurred_at"))),
            summary=str(form.get("summary") or ""),
            idempotency_key=f"ui-{uuid.uuid4()}",
        )
        result = create_crm_event(business_id, payload, db)
    except (ValidationError, ValueError) as exc:
        return _redirect(business_id, error=friendly(exc.errors() if isinstance(exc, ValidationError) else str(exc)))
    except HTTPException as exc:
        return _redirect(business_id, error=friendly(exc.detail))
    return _outcome(business_id, result, "outcome recorded")


@router.post("/ui/businesses/{business_id}/follow-ups")
def follow_up_ui(
    business_id: uuid.UUID,
    reason: str = Form(...),
    due_at: str = Form(...),
    db: Session = Depends(session),
) -> RedirectResponse:
    from lboe_api.main import FollowUpRequest, create_follow_up

    _exists(db, business_id)
    try:
        create_follow_up(business_id, FollowUpRequest(reason=reason, due_at=parse_local_datetime(due_at)), db)
    except (ValidationError, ValueError) as exc:
        return _redirect(business_id, error=friendly(exc.errors() if isinstance(exc, ValidationError) else str(exc)))
    return _redirect(business_id, done="follow-up scheduled")
