"""Provider-neutral discovery contracts and conservative identity helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    campaign_id: UUID
    queries: list[str] = Field(min_length=1, max_length=25)
    geography: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_results: int = Field(default=25, ge=1, le=100)
    timeout_seconds: float = Field(default=300, gt=0, le=3600)
    idempotency_key: str | None = Field(default=None, max_length=300)


class CandidateBusiness(BaseModel):
    """Small normalized discovery record; provider payloads do not cross this boundary."""

    source: str = Field(min_length=1, max_length=80)
    source_id: str | None = Field(default=None, max_length=300)
    display_name: str = Field(min_length=1, max_length=200)
    category: str | None = None
    locality: str | None = None
    address_text: str | None = None
    phone: str | None = None
    website: str | None = None
    source_url: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=0.8, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)


class DiscoveryAdapter(Protocol):
    async def discover(self, request: DiscoveryRequest) -> list[CandidateBusiness]: ...


class DiscoveryValidationError(ValueError):
    """A provider-neutral request cannot be executed as specified."""


@dataclass(frozen=True)
class IdentitySignals:
    source_id: str | None
    phone: str | None
    domain: str | None
    name_locality: str


def normalize_text(value: str | None) -> str | None:
    if not value:
        return None
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split()) or None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    # Short values are extensions/garbage and must not drive a merge.
    return digits if len(digits) >= 7 else None


def normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        host = (urlparse(candidate).hostname or "").casefold().rstrip(".")
    except ValueError:
        return None
    if not host or "." not in host:
        return None
    return host[4:] if host.startswith("www.") else host


def identity_signals(candidate: CandidateBusiness) -> IdentitySignals:
    name = normalize_text(candidate.display_name) or ""
    locality = normalize_text(candidate.locality or candidate.address_text) or ""
    return IdentitySignals(
        source_id=candidate.source_id.strip() if candidate.source_id else None,
        phone=normalize_phone(candidate.phone),
        domain=normalize_domain(candidate.website),
        name_locality=f"{name}|{locality}",
    )
