# Sprint 7 — Human Review and Demo Approval Workflow

Sprint 7 adds the operator control layer around generated concept previews.
It records append-only reviews and checklist items and does not send email,
WhatsApp, SMS, or any other outreach.

Supported decisions are `approve`, `reject`, `request_changes`,
`request_regeneration`, and `mark_needs_manual_edit`. Demo statuses are
distinct from QA: `generated`, `qa_passed`, `qa_failed`, `review_pending`,
`approved`, `rejected`, `changes_requested`, `regeneration_requested`, and
`manual_edit_required`.

Approval requires stored QA to be passed, all artifacts to exist, all twelve
required checklist items to be supplied and passed, and no suppression,
`do_not_contact`, or ambiguous-identity hold. Approval moves
`REVIEW_PENDING → APPROVED_FOR_OUTREACH`; this is only a permissioned
workflow state and does not initiate outreach or consent.

Reject, change, and manual-edit decisions conservatively keep the business in
`REVIEW_PENDING`. Explicit regeneration moves
`REVIEW_PENDING → DEMO_QUEUED` through the lifecycle guard but does not create
a new artifact in Sprint 7. Review history is preserved and exposed with
safe preview metadata, artifact paths, QA summary, and available next actions.

This workflow prepares Sprint 8 for controlled offer/outreach drafting while
keeping human approval and consent gates separate from any future sending.
