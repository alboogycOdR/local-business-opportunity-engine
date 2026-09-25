"""Shared LBOE domain contracts."""

from .audit import (
    AuditAdapter,
    AuditArtifact,
    AuditEvidence,
    AuditFinding,
    AuditRequest,
    AuditResult,
    FakeAuditAdapter,
    WebsiteResolutionResult,
)
from .discovery import (
    CandidateBusiness,
    DiscoveryAdapter,
    DiscoveryRequest,
    DiscoveryValidationError,
    IdentitySignals,
    identity_signals,
    normalize_domain,
    normalize_phone,
    normalize_text,
)
from .fakes import FakeDiscoveryAdapter
from .states import ALLOWED_TRANSITIONS, InvalidTransition, LeadState, transition, validate_transition

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AuditAdapter",
    "AuditArtifact",
    "AuditEvidence",
    "AuditFinding",
    "AuditRequest",
    "AuditResult",
    "CandidateBusiness",
    "DiscoveryAdapter",
    "DiscoveryRequest",
    "DiscoveryValidationError",
    "FakeDiscoveryAdapter",
    "FakeAuditAdapter",
    "IdentitySignals",
    "InvalidTransition",
    "LeadState",
    "identity_signals",
    "normalize_domain",
    "normalize_phone",
    "normalize_text",
    "WebsiteResolutionResult",
    "transition",
    "validate_transition",
]
