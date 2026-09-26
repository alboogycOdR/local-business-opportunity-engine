# Sprint 11 — Manual Reply and CRM Tracking

Sprint 11 records operator-entered CRM outcomes after manual outreach. It
does not read inboxes, sync email/WhatsApp/SMS, classify sentiment, schedule
follow-ups, or generate proposals.

Supported event types are `reply_received`, `meeting_scheduled`,
`proposal_sent`, `won`, `lost`, `no_response_note`, and `manual_note`.
Supported channels are email, WhatsApp, phone, in-person, and manual note.

Substantive events require a summary and enforce the lifecycle:
`CONTACTED → REPLIED → MEETING → PROPOSAL → WON`. A `lost` event is allowed
from contacted, replied, meeting, or proposal states through explicit state
machine edges. No-response notes and manual notes preserve the current state.

Every event is append-only, operator-attributed, timestamped, and marked with
evidence that no external sync was performed. Only an explicit `won` event can
move a proposal to `WON`. Sprint 12 can use these events for reporting and
pilot metrics without introducing inbox automation.
