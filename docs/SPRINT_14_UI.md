# Sprint 14 — Operator UI v1–v4

Implemented the local server-rendered operator cockpit in four compatible
layers:

- v1: dashboard, campaigns, lead detail, reports, safe workflow visibility,
  comments and suppression.
- v2: queues, query filters, controlled artifact previews, bulk dry-run and
  conservative bulk suppression. Approval/readiness/contact/CRM actions are
  never bulk-enabled.
- v3: trusted local operator records, roles, assignments, append-only comments,
  local operator selector, “my queue”, and audit events.
- v4: expiring token-based concept preview links, revocation, safe artifact
  serving, disclaimer enforcement, and hashed access logging.

This is not a public SaaS UI, production hosting, automated sending system, or
CRM/inbox integration. Existing JSON APIs remain unchanged.
