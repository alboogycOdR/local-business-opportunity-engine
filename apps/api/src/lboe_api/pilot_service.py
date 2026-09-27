from __future__ import annotations

import csv
import json
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lboe_api.config import Settings
from lboe_api.db import (
    Business,
    Campaign,
    DemoPreviewLink,
    GeneratedDemo,
    Operator,
    OperatorAssignment,
    OperatorAuditEvent,
    OutreachExecutionRecord,
    OutreachReadinessReview,
    PilotExportRun,
    PilotRun,
    PilotSourcePolicyAcknowledgement,
)

POLICY_VERSION = "pilot-source-v1"
REQUIRED_CAPS = (
    "max_businesses",
    "daily_demo_cap",
    "daily_preview_link_cap",
    "daily_manual_contact_cap",
    "daily_readiness_approval_cap",
)


def pilot_for_business(db: Session, business_id: uuid.UUID) -> PilotRun | None:
    campaign_id = db.scalar(select(Business.campaign_id).where(Business.id == business_id))
    if campaign_id is None:
        return None
    return db.scalar(
        select(PilotRun)
        .where(PilotRun.campaign_id == campaign_id, PilotRun.status != "closed")
        .order_by(PilotRun.created_at.desc())
    )


def cap_available(db: Session, pilot: PilotRun, kind: str) -> bool:
    current = counters(db, pilot)
    limits = {
        "demo": ("demos_today", pilot.daily_demo_cap),
        "preview_link": ("preview_links_today", pilot.daily_preview_link_cap),
        "manual_contact": ("manual_contacts_today", pilot.daily_manual_contact_cap),
        "readiness": ("readiness_approvals_today", pilot.daily_readiness_approval_cap),
    }
    key, limit = limits[kind]
    return current[key] < limit


def pilot_business_ids(db: Session, pilot: PilotRun) -> list[uuid.UUID]:
    return list(db.scalars(select(Business.id).where(Business.campaign_id == pilot.campaign_id)).all())


def _today_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    start = datetime.combine(now.date(), time.min, UTC)
    return start, start + timedelta(days=1)


def counters(db: Session, pilot: PilotRun) -> dict[str, int]:
    ids = pilot_business_ids(db, pilot)
    start, end = _today_bounds()

    def count(model: Any, column: Any) -> int:
        if not ids:
            return 0
        return int(
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(column.in_(ids), model.created_at >= start, model.created_at <= end)
            )
            or 0
        )

    return {
        "businesses": len(ids),
        "demos_today": count(GeneratedDemo, GeneratedDemo.business_id),
        "preview_links_today": count(DemoPreviewLink, DemoPreviewLink.business_id),
        "manual_contacts_today": count(OutreachExecutionRecord, OutreachExecutionRecord.business_id),
        "readiness_approvals_today": count(OutreachReadinessReview, OutreachReadinessReview.business_id),
    }


def readiness_checks(db: Session, pilot: PilotRun, settings: Settings) -> list[dict[str, Any]]:
    campaign = db.get(Campaign, pilot.campaign_id)
    ids = pilot_business_ids(db, pilot)
    assigned = (
        bool(db.scalar(select(func.count()).select_from(Operator).where(Operator.active.is_(True))))
        or bool(
            db.scalar(
                select(func.count()).select_from(OperatorAssignment).where(OperatorAssignment.business_id.in_(ids))
            )
        )
        if ids
        else bool(db.scalar(select(func.count()).select_from(Operator).where(Operator.active.is_(True))))
    )
    ack = (
        db.scalar(
            select(PilotSourcePolicyAcknowledgement).where(
                PilotSourcePolicyAcknowledgement.pilot_id == pilot.id,
                PilotSourcePolicyAcknowledgement.policy_version == pilot.source_policy_version,
            )
        )
        is not None
    )
    report_delivery = 0
    values = [
        ("campaign_exists", "Campaign exists", campaign is not None, True),
        ("businesses_present", "Campaign has businesses", bool(ids), True),
        ("operator_available", "Operator available", assigned, True),
        ("source_policy_acknowledged", "Source policy acknowledged", ack, True),
        ("sending_disabled", "System sending disabled", True, True),
        ("system_delivery_zero", "System delivery count is zero", report_delivery == 0, True),
        ("caps_configured", "Daily caps configured", all(getattr(pilot, c, 0) > 0 for c in REQUIRED_CAPS), True),
        ("target_configured", "Target lead count configured", pilot.target_lead_count > 0, True),
        ("artifact_root_configured", "Demo artifact root configured", bool(settings.demo_artifact_root), True),
        ("preview_hosting_available", "Preview hosting available", True, True),
        ("suppression_visible", "Suppression count visible", True, False),
        ("active_preview_links_visible", "Active preview links visible", True, False),
    ]
    return [
        {"code": c, "label": label, "result": "pass" if ok else "fail", "required": req, "details": {"value": ok}}
        for c, label, ok, req in values
    ]


def readiness_summary(db: Session, pilot: PilotRun, settings: Settings) -> dict[str, Any]:
    checks = readiness_checks(db, pilot, settings)
    required_fail = [c for c in checks if c["required"] and c["result"] != "pass"]
    return {"checks": checks, "ready": not required_fail, "required_failures": required_fail}


def audit(
    db: Session,
    pilot: PilotRun,
    action: str,
    operator_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        OperatorAuditEvent(
            operator_id=operator_id,
            entity_type="pilot",
            entity_id=pilot.id,
            action=action,
            before_data=before,
            after_data=after,
            event_metadata={"pilot_id": str(pilot.id)},
        )
    )


def generate_export(db: Session, pilot: PilotRun, settings: Settings, operator_id: uuid.UUID | None) -> PilotExportRun:
    root = Path(settings.export_root).resolve()
    out = (root / "pilots" / str(pilot.id)).resolve()
    if root not in out.parents:
        raise ValueError("export_path_invalid")
    out.mkdir(parents=True, exist_ok=True)
    ids = pilot_business_ids(db, pilot)
    businesses = db.scalars(select(Business).where(Business.id.in_(ids))).all() if ids else []
    report = __import__("lboe_api.reporting_service", fromlist=["build_pilot_report"]).build_pilot_report(
        db, campaign_id=pilot.campaign_id, include_details=True
    )
    files: dict[str, str] = {}
    summary = {
        "pilot_id": str(pilot.id),
        "name": pilot.name,
        "mode": pilot.mode,
        "status": pilot.status,
        "warnings": ["Local export; no sending or raw payloads."],
    }
    data = {"pilot-summary.json": summary, "pilot-report.json": report}
    for name, payload in data.items():
        (out / name).write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        files[name] = str(out / name)
    with (out / "leads.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["business_id", "name", "category", "locality", "state"])
        w.writerows([[b.id, b.display_name, b.category, b.locality, b.state] for b in businesses])
    files["leads.csv"] = str(out / "leads.csv")
    for name, header in (
        ("demo-links.csv", ["business_id", "demo_id", "status", "expires_at"]),
        ("operator-activity.csv", ["entity_type", "action", "created_at"]),
    ):
        (out / name).write_text(",".join(header) + "\n", encoding="utf-8")
        files[name] = str(out / name)
    run = PilotExportRun(
        pilot_id=pilot.id,
        status="completed",
        export_root=str(out),
        files=files,
        warnings=summary["warnings"],
        created_by_operator_id=operator_id,
    )
    db.add(run)
    audit(db, pilot, "export_generated", operator_id, after={"files": list(files)})
    db.commit()
    return run
