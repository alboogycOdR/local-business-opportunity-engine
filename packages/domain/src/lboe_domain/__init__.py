"""Shared LBOE domain contracts."""

from .discovery import (
    CandidateBusiness,
    DiscoveryAdapter,
    DiscoveryRequest,
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
    "CandidateBusiness",
    "DiscoveryAdapter",
    "DiscoveryRequest",
    "FakeDiscoveryAdapter",
    "IdentitySignals",
    "InvalidTransition",
    "LeadState",
    "identity_signals",
    "normalize_domain",
    "normalize_phone",
    "normalize_text",
    "transition",
    "validate_transition",
]
