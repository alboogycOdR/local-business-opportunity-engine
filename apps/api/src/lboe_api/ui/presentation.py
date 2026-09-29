"""Operator-facing presentation helpers: local time, readable labels, and error pages."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from lboe_api.main import settings


def display_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.display_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def fmt_dt(value: datetime | None, *, with_time: bool = True) -> str:
    """Format a timestamp in the operator's timezone; naive values are stored UTC."""
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    local = value.astimezone(display_zone())
    return local.strftime("%d %b %Y, %H:%M" if with_time else "%d %b %Y")


def parse_local_datetime(value: str) -> datetime:
    """Parse an ``<input type=datetime-local>`` value entered in the operator's timezone."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=display_zone())
    return parsed.astimezone(UTC)


def local_input_value(value: datetime) -> str:
    return value.astimezone(display_zone()).strftime("%Y-%m-%dT%H:%M")


STATE_LABELS = {
    "DISCOVERED": "Discovered",
    "DEDUPED": "De-duplicated",
    "QUALIFIED": "Qualified",
    "REJECTED": "Rejected",
    "ENRICHING": "Enriching",
    "ENRICHED": "Enriched",
    "ENRICHMENT_FAILED": "Enrichment failed",
    "AUDITING": "Auditing",
    "AUDITED": "Audited",
    "SCORED": "Scored",
    "ARCHIVED": "Archived",
    "DEMO_QUEUED": "Concept queued",
    "DEMO_GENERATED": "Concept generated",
    "QA_FAILED": "Concept failed QA",
    "REVIEW_PENDING": "Awaiting concept review",
    "APPROVED_FOR_OUTREACH": "Concept approved — draft outreach",
    "CONSENT_PENDING": "Awaiting consent decision",
    "OUTREACH_READY": "Cleared for manual contact",
    "CONTACTED": "Contacted (manually)",
    "REPLIED": "Replied",
    "MEETING": "Meeting",
    "PROPOSAL": "Proposal",
    "WON": "Won",
    "LOST": "Lost",
    "SUPPRESSED": "Suppressed — do not contact",
}

STATUS_LABELS = {
    "qa_passed": "Passed QA — awaiting review",
    "qa_failed": "Failed QA — sharing blocked",
    "review_pending": "Awaiting review",
    "approved": "Approved",
    "rejected": "Rejected",
    "changes_requested": "Changes requested",
    "regeneration_requested": "Regeneration requested",
    "manual_edit_required": "Manual edit required",
    "rendering": "Rendering",
    "draft": "Draft",
    "ready": "Ready",
    "blocked": "Blocked",
    "archived": "Archived",
}

ACTION_LABELS = {
    "generate_demo": "Generate concept preview",
    "conversion_upgrade_offer": "Conversion upgrade",
    "technical_cleanup_offer": "Technical cleanup",
    "score_only": "Score only",
    "audit_required": "Audit required",
    "manual_review": "Manual review",
    "do_not_contact": "Do not contact",
    "archive": "Archive",
}


def state_label(value: str | None) -> str:
    return STATE_LABELS.get(value or "", (value or "").replace("_", " ").capitalize())


def status_label(value: str | None) -> str:
    return STATUS_LABELS.get(value or "", (value or "").replace("_", " ").capitalize())


def action_label(value: str | None) -> str:
    return ACTION_LABELS.get(value or "", (value or "").replace("_", " ").capitalize())


# Machine-readable API codes -> sentences an operator can act on.
FRIENDLY_ERRORS = {
    "business_not_found": "That business no longer exists or the link is wrong.",
    "campaign_not_found": "That campaign no longer exists or the link is wrong.",
    "demo_not_found": "That concept preview no longer exists.",
    "proposal_not_found": "That proposal pack no longer exists.",
    "pilot_not_found": "That pilot no longer exists.",
    "queue_not_found": "There is no queue with that name.",
    "demo_not_shareable": "Only concept previews that passed QA can be shared. Fix or regenerate this concept first.",
    "business_suppressed": "This business is suppressed. Nothing can be shared with or sent to it.",
    "pilot_preview_link_cap_reached": "Today's preview-link cap for this pilot has been reached.",
    "proposal_review_required": "Approve the proposal pack before exporting it.",
    "invalid_proposal_review": "Choose a review decision and enter the reviewer's name.",
    "proposal_safety_checks_failed": "The proposal cannot be approved while a safety check is failing.",
    "unsupported_bulk_action": "That bulk action is not available.",
    "invalid_pilot_config": "Every pilot cap and target must be greater than zero.",
    "pilot_readiness_failed": "The pilot is not ready yet. Resolve the failing readiness checks first.",
    "invalid_pilot_transition": "The pilot cannot move to that status from its current status.",
    "pilot_not_mutable": "Closed pilots cannot be changed, and caps must be greater than zero.",
    "demo_qa_not_passed": "The concept must pass every QA check before it can be approved.",
    "demo_artifact_missing": "The concept files are missing. Regenerate the concept.",
    "checklist_incomplete": "Every review checklist item must be confirmed before approval.",
    "ambiguous_identity": "The business identity is ambiguous. Resolve it before approval.",
    "do_not_contact_hold": "A do-not-contact hold applies to this business.",
    "invalid_transition": "That step is not allowed from the business's current stage.",
    "invalid_operator_token": "That operator token is not valid.",
    "active_operator_required": "Create an active operator before signing in.",
}


def friendly(detail: Any) -> str:
    if isinstance(detail, dict):
        code = str(detail.get("error") or detail.get("reason") or "")
        return FRIENDLY_ERRORS.get(code, code.replace("_", " ").capitalize() or "The request could not be completed.")
    if isinstance(detail, list):
        fields = sorted({str(item.get("loc", ["", "field"])[-1]) for item in detail if isinstance(item, dict)})
        return "Please check these fields: " + ", ".join(fields) if fields else "Some fields are invalid."
    code = str(detail or "")
    return FRIENDLY_ERRORS.get(code, code.replace("_", " ").capitalize() or "The request could not be completed.")


def _prospect_error(status: int) -> HTMLResponse:
    message = (
        "This preview link has expired or has been withdrawn."
        if status == 410
        else "This preview is not available. Please check the link you were sent."
    )
    body = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex, nofollow'><title>Preview unavailable</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;"
        "padding:0 1rem;color:#17202a}</style>"
        f"</head><body><main><h1>Preview unavailable</h1><p>{html.escape(message)}</p></main></body></html>"
    )
    return HTMLResponse(body, status_code=status, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


def _back_link(request: Request) -> str:
    """Link back to the operator page the request came from (same-site /ui paths only)."""
    referer = urlsplit(request.headers.get("referer", ""))
    if referer.path.startswith("/ui") and referer.netloc in {"", request.url.netloc}:
        target = referer.path + (f"?{referer.query}" if referer.query else "")
        return f"<a class='button button-secondary' href='{html.escape(target)}'>Go back</a> "
    return ""


async def ui_http_exception_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    path = request.url.path
    if path.startswith("/preview/"):
        return _prospect_error(exc.status_code)
    if not path.startswith("/ui"):
        return await http_exception_handler(request, exc)
    from lboe_api.ui.routes import page

    title = {404: "Not found", 409: "Action not available", 410: "No longer available"}.get(
        exc.status_code, "Something went wrong"
    )
    response = page(
        title,
        f"<div class='warning' role='alert'>{html.escape(friendly(exc.detail))}</div>"
        f"<p>{_back_link(request)}<a class='button button-secondary' href='/ui'>Dashboard</a></p>",
    )
    response.status_code = exc.status_code
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def ui_validation_exception_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    if not request.url.path.startswith("/ui"):
        return await request_validation_exception_handler(request, exc)
    from lboe_api.ui.routes import page

    response = page(
        "Please check the form",
        f"<div class='warning' role='alert'>{html.escape(friendly(exc.errors()))}</div><p>{_back_link(request)}</p>",
    )
    response.status_code = 422
    return response
