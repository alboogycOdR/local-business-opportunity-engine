"""Provider-neutral pilot reporting contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class PilotReportWindow(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class FunnelStageMetric(BaseModel):
    stage: str
    count: int


class ConversionMetric(BaseModel):
    code: str
    numerator: int
    denominator: int
    rate: float | None = None


class OperatorWorkloadMetric(BaseModel):
    operator: str
    category: str
    count: int


class QualityMetric(BaseModel):
    code: str
    count: int
    details: dict[str, Any] = Field(default_factory=dict)


class PilotReportRequest(BaseModel):
    campaign_id: uuid.UUID | None = None
    vertical: str | None = None
    window: PilotReportWindow = Field(default_factory=PilotReportWindow)
    include_details: bool = False


class PilotReportResult(BaseModel):
    campaign_id: uuid.UUID | None = None
    vertical: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    generated_at: datetime
    funnel_metrics: list[FunnelStageMetric]
    conversion_metrics: list[ConversionMetric]
    quality_metrics: list[QualityMetric]
    workload_metrics: list[OperatorWorkloadMetric]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
