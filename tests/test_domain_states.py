import pytest
from lboe_domain import InvalidTransition, LeadState, validate_transition


def test_valid_transition() -> None:
    validate_transition(LeadState.DISCOVERED, LeadState.DEDUPED)


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(InvalidTransition):
        validate_transition(LeadState.DISCOVERED, LeadState.WON)
