# Operator UI

The local operator cockpit is a thin server-rendered layer over the existing
FastAPI workflow. It does not replace API validation or lifecycle guards.

## Routes

- `/ui` — dashboard and safety banner
- `/ui/campaigns` and `/ui/campaigns/{id}` — campaign queue and filters
- `/ui/businesses/{id}` — lead detail, notes, assignment, suppression, and safe next actions
- `/ui/queues/*` — demo review, draft, readiness, manual contact, and CRM queues
- `/ui/reports/pilot` — global and campaign reports
- `/ui/operators` and `/ui/my-queue` — trusted local operator workspace
- `/ui/demos/{id}/preview` — controlled internal artifact preview
- `/ui/pilots` — pilot configuration, readiness, caps, exports, and retrospective

Pilot pages show dry-run versus active mode, require source-policy acknowledgement
before readiness, and keep exports local under `LBOE_EXPORT_ROOT`. Dry-run is an
operator UI guardrail; the underlying JSON logging APIs remain unchanged.

The UI always shows that system delivery is disabled. Manual outreach remains
an operator assertion and `system_delivery_count` remains zero.

## Roles and audit trail

Local operator records support `owner`, `manager`, `operator`, `reviewer`, and
`viewer` roles. v3 records assignments, append-only comments, and UI audit
events. This is trusted local mode, not production authentication.

## Preview sharing

Approved or QA-passed demos can receive expiring external preview links. Raw
tokens are shown once and only their SHA-256 hashes are stored. Links can be
revoked and every successful/blocked access is logged.
