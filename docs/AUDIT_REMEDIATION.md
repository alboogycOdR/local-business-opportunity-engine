# Audit remediation: operator and API integration

This document records the API/operator-console changes made from the audit at `cc56bda` and the joined G1–G3 worktree. The console remains server rendered. Sending, inbox sync, external CRM sync, and credential storage remain disabled.

## Implemented in G4

- UI sessions now close deterministically. Dashboard/card data is batched, lists are paginated, campaign lead counts are aggregated, and same-named campaigns stay individually visible.
- The operator console now presents stage-aware next steps, prominent non-actionable suppression state, review/consent/contact/CRM/follow-up workflow forms, readable labels and local times, accessible landmarks/forms/table regions, mobile navigation styling, and readable HTML errors.
- External concept previews are self-contained and styled, carry noindex/no-store/CSP headers, reject suppressed businesses and non-shareable demo states, and suppression revokes active links. Maps are local by default; Google Maps opens only after an operator clicks the explicit external link.
- Dry-run pilots block manual contact logs and CRM outcome writes at the API boundary. Active-pilot manual records remain operator assertions; LBOE does not deliver messages.
- Discovery, website audit, and enrichment now create durable queued PostgreSQL jobs, then publish only `job_id` to `lboe:jobs:v1`. The consumer group and worker statuses follow `lboe-workers` and `queued → running → succeeded|failed`. A duplicate request returns the existing job ID; a still-queued row can be republished after Redis outage, while the worker's row lock/status guard prevents duplicate execution. `/v1/jobs/{job_id}` and the UI job page expose status, safe result, or safe error class.
- `/health` now checks PostgreSQL with the configured bounded pool acquisition timeout. `/ready` retains PostgreSQL and Redis checks.

## Worker artifacts and health integration

For local Compose development, the API process and worker must resolve the same host `artifacts/` directory. Compose mounts `./artifacts` at `/app/artifacts` for the worker; configure the API's `LBOE_AUDIT_ARTIFACT_ROOT` to the host path corresponding to `/app/artifacts/audits`. The worker stores audit screenshots in per-run directories below that root.

Production must mount a shared persistent filesystem or object-backed volume at the same configured artifact root for both API and worker. If API and worker see different paths, artifact rows may exist while the API cannot serve the associated files. Do not use an ephemeral worker filesystem.

The repository Compose file does not define an API service. Deployment configuration must attach a health check to the actual API container that calls `/health` and restarts an unhealthy process; the application cannot configure a Compose health check for a service absent from this Compose file. `/ready` is suitable for dependency readiness but may be too strict for a liveness probe when Redis is temporarily unavailable.

## Residual work and acceptance notes

- The audit's performance patch reported the campaign report scoping improvement, but the broader report aggregation rewrite is deferred: populated before/after golden equivalence data was unavailable. Do not treat the 10k-lead report residual as closed.
- The audit's 43 regression tests were written against synchronous discovery/audit/enrichment responses. G4 intentionally changes those three endpoints to queued responses per the approved Redis worker contract. Such tests must be bridged by an owned test-only worker harness or updated acceptance assertions; production code must not execute those jobs inline just to satisfy the old synchronous assumptions.
- Proposal and delivery workflow forms are available in the operator UI. Full inbox-style queue refinement and a broader Jinja autoescaping migration remain hardening work.
- Operator identity is still a typed name in several decisions. This change does not add a new authentication/authorization model.
- Audit security workstreams were not run. UX/performance audit results are not a security review or production-readiness sign-off.
- Validate PostgreSQL migration/type parity separately using a disposable database; never apply audit migrations to a prospect or production database as part of this remediation.

## G4 validation record

- Focused integration tests: `python -m pytest tests/test_audit_remediation.py tests/test_api_discovery.py tests/test_openapi.py -q` — **5 passed**.
- Joined project tests: `python -m pytest tests` — **60 passed**.
- Ruff check and format check: **passed**; `git diff --check`: **passed**.
- Focused mypy over the changed API/UI modules and owned tests: **passed**. Full `mypy apps packages integrations tests` remains blocked by duplicate `conftest` module names in the pre-existing integration and worker test directories.
- Audit regression suite, run against the joined checkout with `LBOE_AUDIT_TARGET` set: **28 passed, 15 failed**. The 15 failing seed-based UX/performance tests require synchronous discovery/audit/enrichment completion or data derived from it. The current endpoints correctly create queued jobs and return `503 job_queue_unavailable` when the audit fixture has no Redis/worker. The unchanged audit suite has no bridge to process those jobs. No production behavior was made synchronous to silence this fixture mismatch; the audit suite therefore remains partially red pending its asynchronous test harness/acceptance updates.
- `docker compose config`: passed. No G4 schema change was made, so G4 did not apply migrations. The G1 schema changes were verified separately against a disposable PostgreSQL database.
