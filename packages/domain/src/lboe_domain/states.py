"""Authoritative lead lifecycle and transition guards."""

from enum import StrEnum
from typing import Final


class LeadState(StrEnum):
    DISCOVERED = "DISCOVERED"
    DEDUPED = "DEDUPED"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    ENRICHING = "ENRICHING"
    ENRICHED = "ENRICHED"
    ENRICHMENT_FAILED = "ENRICHMENT_FAILED"
    AUDITING = "AUDITING"
    AUDITED = "AUDITED"
    SCORED = "SCORED"
    ARCHIVED = "ARCHIVED"
    DEMO_QUEUED = "DEMO_QUEUED"
    DEMO_GENERATED = "DEMO_GENERATED"
    QA_FAILED = "QA_FAILED"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED_FOR_OUTREACH = "APPROVED_FOR_OUTREACH"
    CONSENT_PENDING = "CONSENT_PENDING"
    OUTREACH_READY = "OUTREACH_READY"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    WON = "WON"
    LOST = "LOST"
    SUPPRESSED = "SUPPRESSED"


# Explicit edges keep lifecycle changes auditable and prevent callers from
# skipping qualification, consent, or human review gates.
ALLOWED_TRANSITIONS: Final[dict[LeadState, frozenset[LeadState]]] = {
    # Lightweight website audits may run before enrichment; this edge is
    # explicit and auditable, while deep enrichment remains a separate path.
    LeadState.DISCOVERED: frozenset({LeadState.DEDUPED, LeadState.REJECTED, LeadState.AUDITING}),
    LeadState.DEDUPED: frozenset({LeadState.QUALIFIED, LeadState.REJECTED}),
    LeadState.QUALIFIED: frozenset({LeadState.ENRICHING, LeadState.REJECTED}),
    LeadState.ENRICHING: frozenset({LeadState.ENRICHED, LeadState.ENRICHMENT_FAILED}),
    LeadState.ENRICHMENT_FAILED: frozenset({LeadState.ENRICHING, LeadState.ARCHIVED}),
    LeadState.ENRICHED: frozenset({LeadState.AUDITING}),
    LeadState.AUDITING: frozenset({LeadState.AUDITED, LeadState.ENRICHMENT_FAILED}),
    LeadState.AUDITED: frozenset({LeadState.SCORED}),
    LeadState.SCORED: frozenset({LeadState.ARCHIVED, LeadState.DEMO_QUEUED}),
    LeadState.DEMO_QUEUED: frozenset({LeadState.DEMO_GENERATED, LeadState.QA_FAILED}),
    LeadState.QA_FAILED: frozenset({LeadState.DEMO_QUEUED, LeadState.ARCHIVED}),
    LeadState.DEMO_GENERATED: frozenset({LeadState.REVIEW_PENDING}),
    # Human review may send a demo back through the controlled generation
    # queue when the operator explicitly requests regeneration.
    LeadState.REVIEW_PENDING: frozenset({LeadState.REJECTED, LeadState.APPROVED_FOR_OUTREACH, LeadState.DEMO_QUEUED}),
    LeadState.APPROVED_FOR_OUTREACH: frozenset({LeadState.CONSENT_PENDING, LeadState.SUPPRESSED}),
    LeadState.CONSENT_PENDING: frozenset({LeadState.OUTREACH_READY, LeadState.SUPPRESSED}),
    LeadState.OUTREACH_READY: frozenset({LeadState.CONTACTED, LeadState.SUPPRESSED}),
    LeadState.CONTACTED: frozenset({LeadState.REPLIED, LeadState.SUPPRESSED}),
    LeadState.REPLIED: frozenset({LeadState.MEETING, LeadState.SUPPRESSED}),
    LeadState.MEETING: frozenset({LeadState.PROPOSAL, LeadState.SUPPRESSED}),
    LeadState.PROPOSAL: frozenset({LeadState.WON, LeadState.LOST}),
}

# Suppression is an operator safety hold and may be applied from any active
# state, including a lead that has not yet reached outreach.
for _state in LeadState:
    if _state not in {LeadState.SUPPRESSED, LeadState.WON, LeadState.LOST}:
        ALLOWED_TRANSITIONS[_state] = ALLOWED_TRANSITIONS.get(_state, frozenset()) | {LeadState.SUPPRESSED}


class InvalidTransition(ValueError):
    """Raised when a lead attempts a transition not in the lifecycle graph."""


def validate_transition(current: LeadState, target: LeadState) -> None:
    """Raise :class:`InvalidTransition` unless ``current -> target`` is allowed."""
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(f"transition {current.value} -> {target.value} is not allowed")


def transition(current: LeadState, target: LeadState) -> LeadState:
    validate_transition(current, target)
    return target
