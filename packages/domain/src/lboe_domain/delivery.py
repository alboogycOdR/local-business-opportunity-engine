"""Contracts for operator-managed client delivery projects."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DeliveryStatus = Literal[
    "draft",
    "intake_pending",
    "content_pending",
    "build_ready",
    "in_progress",
    "client_review",
    "approved",
    "delivered",
    "closed",
    "cancelled",
]


class DeliveryProjectRequest(BaseModel):
    proposal_package_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    summary: str = ""


class DeliveryChecklistRequest(BaseModel):
    category: Literal["intake", "access_assets"]
    code: str = Field(min_length=1)
    status: Literal["pending", "received", "verified", "not_applicable"] = "pending"
    notes: str = ""


class DeliveryMilestoneRequest(BaseModel):
    milestone_type: str = Field(min_length=1)
    status: Literal["pending", "complete", "blocked"] = "complete"
    note: str = ""


class DeliveryApprovalRequest(BaseModel):
    approval_type: str
    approved_item: str
    client_assertion: str = ""
    notes: str = ""
    artifact_reference: str | None = None


class DeliveryExportResult(BaseModel):
    project_id: uuid.UUID
    files: dict[str, str]
    created_at: datetime
