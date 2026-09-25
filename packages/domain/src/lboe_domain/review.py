"""Provider-neutral contracts for human review of concept demos."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ReviewDecision = Literal[
    "approve",
    "reject",
    "request_changes",
    "request_regeneration",
    "mark_needs_manual_edit",
]


class DemoReviewChecklist(BaseModel):
    code: str
    label: str
    passed: bool
    notes: str | None = None


class DemoReviewRequest(BaseModel):
    decision: ReviewDecision
    reviewer: str = Field(min_length=1, max_length=200)
    notes: str = ""
    checklist: list[DemoReviewChecklist] = Field(default_factory=list)


class DemoReviewNote(BaseModel):
    reviewer: str
    notes: str


class DemoReviewResult(BaseModel):
    id: uuid.UUID
    demo_id: uuid.UUID
    business_id: uuid.UUID
    decision: ReviewDecision
    reviewer: str
    notes: str
    checklist: list[DemoReviewChecklist]
    created_at: datetime
    resulting_demo_status: str
    resulting_business_state: str
