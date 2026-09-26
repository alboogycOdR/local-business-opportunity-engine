from datetime import UTC, datetime
from uuid import uuid4

from lboe_domain import LeadResponseLogRequest, LeadState, validate_transition


def test_crm_contract_and_lifecycle_edges() -> None:
    request = LeadResponseLogRequest(
        event_type="reply_received",
        channel="email",
        operator="operator",
        occurred_at=datetime.now(UTC),
        summary="Reply recorded manually.",
        outreach_execution_record_id=uuid4(),
    )
    assert request.event_type == "reply_received"
    validate_transition(LeadState.CONTACTED, LeadState.REPLIED)
    validate_transition(LeadState.REPLIED, LeadState.MEETING)
    validate_transition(LeadState.MEETING, LeadState.PROPOSAL)
    validate_transition(LeadState.PROPOSAL, LeadState.WON)
    validate_transition(LeadState.CONTACTED, LeadState.LOST)
