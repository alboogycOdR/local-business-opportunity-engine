# Audit remediation: operator and API integration

This document records the API/operator-console changes made from the audit at `cc56bda` and the joined G1–G3 worktree. The console remains server rendered. Sending, inbox sync, external CRM sync, and credential storage remain disabled.

## Implemented in G4

- UI sessions now close deterministically. Dashboard/card data is batched, lists are paginated, campaign lead counts are aggregated, and same-named campaigns stay individually visible.
- The operator console now presents stage-aware next steps, prominent non-actionable suppression state, review/consent/contact/CRM/follow-up workflow forms, readable labels and local times, accessible landmarks/forms/table regions, mobile navigation styling, and readable HTML errors.
- External concept previews are self-contained and styled, carry noindex/no-store/CSP headers, reject suppressed businesses and non-shareable demo states, and suppression revokes active links. Maps are local by default; Google Maps opens only after an operator clicks the explicit external link.
- Dry-run pilots block manual contact logs and CRM outcome writes at the API boundary. Active-pilot manual records remain operator assertions; LBOE does not deliver messages.
- Discovery, website audit, and enrichment now create durable queued PostgreSQL jobs, then publish only `job_id` to `lboe:jobs:v1`. The consumer group and worker statuses follow `lboe-workers` and `queued → running → succeeded|failed`. A duplicate request returns the existing job ID; a still-queued row can be republished after Redis outage, while the worker's row lock/status guard prevents duplicate execution. `/v1/jobs/{job_id}` and the UI job page expose status, safe result, or safe error class.
- The worker periodically reconciles aged `queued` PostgreSQL rows back into Redis. Short-lived Redis markers bound recovery duplicates, and the PostgreSQL status claim remains authoritative. This closes the commit-then-publish gap when Redis fails and the original caller never retries.
- `/health` now checks PostgreSQL with the configured bounded pool acquisition timeout. `/ready` retains PostgreSQL and Redis checks.
- When `LBOE_AUTH_ENABLED=true`, `/v1/*` now requires `Authorization: Bearer $LBOE_OPERATOR_AUTH_TOKEN`; `/health` and `/ready` remain unauthenticated probes. Authenticated UI writes validate same-origin requests and the stored CSRF cookie hash when `LBOE_CSRF_ENABLED=true`.
- A production process now refuses to start unless authentication and CSRF are enabled, both operator and signing secrets are at least 32 characters with the default signing secret replaced, and cookies are marked secure. Development settings remain permissive for local bootstrap.
- Homepage enrichment now validates the initial URL and every redirect against the existing public-address SSRF policy, disables automatic redirects, rejects loops, and caps accepted HTML at 2 MB.

## Worker artifacts and health integration

For local Compose development, the API process and worker must resolve the same host `artifacts/` directory. Compose mounts `./artifacts` at `/app/artifacts` for the worker; configure the API's `LBOE_AUDIT_ARTIFACT_ROOT` to the host path corresponding to `/app/artifacts/audits`. The worker stores audit screenshots in per-run directories below that root.

Production must mount a shared persistent filesystem or object-backed volume at the same configured artifact root for both API and worker. If API and worker see different paths, artifact rows may exist while the API cannot serve the associated files. Do not use an ephemeral worker filesystem.

The repository Compose file does not define an API service. Deployment configuration must attach a health check to the actual API container that calls `/health` and restarts an unhealthy process; the application cannot configure a Compose health check for a service absent from this Compose file. `/ready` is suitable for dependency readiness but may be too strict for a liveness probe when Redis is temporarily unavailable.

## Residual work and acceptance notes

- Pilot report generation now uses grouped SQL queries and counts instead of materializing in-scope business and operational rows. A populated, fully synthetic 10,000-business PostgreSQL golden comparison produced identical report payloads for all six cases. Baseline cases took 112.145–114.555 seconds; remediated cases took 0.263–0.396 seconds. No prospect or production data was used.
- The audit's 43 regression tests were written against synchronous discovery/audit/enrichment responses. `tests/audit_inline_worker.py` is a test-only bridge for the deterministic offline audit adapter, leaving production endpoints queued. Run the audit tests with `-p audit_inline_worker` to validate downstream workflow states without Redis; queue behavior is separately covered by project tests.
- Proposal and delivery workflow forms are available in the operator UI. Full inbox-style queue refinement and a broader Jinja autoescaping migration remain hardening work.
- Operator identity is still a typed name in several decisions. This change does not add a new authentication/authorization model.
- The supplied audit covers UX/performance, not its other listed workstreams. A focused source review found and closed API access-control, UI CSRF, and unsafe production-configuration gaps. A formal independent penetration test and organization-specific threat model remain release activities; this remediation is not a production security certification.
- The focused threat model, closed findings, and residual deployment controls are recorded in `docs/SECURITY_REVIEW_2026-09-30.md`.
- Validate PostgreSQL migration/type parity separately using a disposable database; never apply audit migrations to a prospect or production database as part of this remediation.

## G4 validation record

- Combined project tests: `python -m pytest tests apps/worker/tests integrations/website_auditor/tests` — **71 passed**, including the synthetic 10k-business aggregation check, auth/CSRF/production-configuration regressions, queue reconciliation, and enrichment SSRF checks.
- Focused integration tests: `python -m pytest tests/test_audit_remediation.py tests/test_api_discovery.py tests/test_openapi.py -q` — **7 passed**.
- Ruff check and format check: **passed**; `git diff --check`: **passed**.
- Full mypy: `mypy apps packages integrations tests` — **passed (74 source files)**. The mypy configuration excludes only the nested test `conftest.py` files that collide under the same top-level module name; worker and integration test modules remain checked.
- Audit regression suite, run against the joined checkout using `LBOE_AUDIT_TARGET` and the owned test-only bridge in `tests/audit_inline_worker.py`: **43 passed**. Production job endpoints remain asynchronous; the deterministic offline adapter only runs inline inside this test plugin.
- Pilot report aggregation is covered by reporting unit tests, the audit scope regression, and the populated PostgreSQL golden comparison above.

To rerun the unchanged audit pack from PowerShell, set `LBOE_AUDIT_TARGET` to this checkout, prepend its `tests` directory to `PYTHONPATH`, and run `python -m pytest -p audit_inline_worker -c <audit-root>/tests/pytest.ini <audit-root>/tests`. The pack remains unmodified in `audit/`.
- `docker compose config`: passed. No G4 schema change was made, so G4 did not apply migrations. The G1 schema changes were verified separately against a disposable PostgreSQL database.
