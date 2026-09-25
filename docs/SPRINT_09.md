# Sprint 9 — Consent and Outreach Readiness Workflow

Sprint 9 adds an explicit operator-controlled readiness layer between
approved outreach drafts and any future manual sending. It never sends a
message, calls a delivery provider, or moves a business to `CONTACTED`.

Readiness reviews are append-only and record selected channels, channel-level
message approvals, consent-basis metadata, deterministic checks, reviewer,
notes, and the resulting lifecycle state.

Supported consent-basis values are `manual_operator_review`,
`existing_relationship`, `explicit_permission_recorded`,
`public_business_contact_for_manual_outreach`, `do_not_contact`, and
`unknown`. `unknown` cannot produce `OUTREACH_READY`. Explicit permission,
an existing relationship, or public business contact for manual operator
outreach require operator notes. This metadata is an operational control, not
legal advice or a legal determination.

`prepare_consent_review` moves `APPROVED_FOR_OUTREACH → CONSENT_PENDING`.
`approve_for_manual_outreach` selects and approves only the requested draft
channels and moves to `OUTREACH_READY`. Rejecting or requesting draft changes
does not approve messages. `suppress_business` uses the existing suppression
mechanism and moves through the lifecycle guard to `SUPPRESSED`.

Readiness requires a ready draft package, selected non-empty messages, passed
draft safety checks, no suppression, no policy or ambiguity hold, supported
channels, and a named reviewer. The operator remains responsible for any
future consent and manual action. Sprint 10 may add execution controls while
preserving the no-automatic-sending boundary.
