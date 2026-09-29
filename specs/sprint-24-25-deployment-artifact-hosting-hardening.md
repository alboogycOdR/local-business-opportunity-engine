# Work Batch 4 — Sprint 24–25: Deployment + Artifact Hosting Hardening

## Current baseline

Start from the accepted Sprint 22–23 commit after Work Batch 3 is complete.

Do not start Sprint 26.

## Goal

Prepare LBOE for safer non-local operation and durable artifact handling.

This batch has two parts:

```text
Sprint 24: Deployment readiness, authentication/security hardening
Sprint 25: Artifact hosting/storage hardening
```

This is not a public SaaS launch. It is hardening for controlled internal deployment.

## Non-goals

Do not add automated sending, email/WhatsApp/SMS sending, inbox sync, CRM sync, payments, billing, full public SaaS launch, multi-tenant billing/accounting, or Sprint 26 work.

## Sprint 24 — Deployment Readiness / Security Hardening

### Goals

1. Move beyond local-only assumptions for internal deployment.
2. Add proper authentication if not already present.
3. Harden sessions, CSRF, roles, and deployment configuration.
4. Document safe deployment boundaries.

### Authentication and sessions

Add or improve login/logout, session cookies, secure cookie settings, CSRF tokens for mutating UI forms, password hashing or trusted SSO placeholder depending on scope, operator identity binding, and role enforcement review.

If full auth is too large, implement a minimal internal auth layer with clear limitations.

### Role enforcement

Review and harden viewer, operator, reviewer, manager, and owner roles.

Sensitive actions requiring manager/owner should include activate pilot, override dry-run blocks, suppress business, approve external preview sharing, revoke preview links if ownership matters, bulk actions, and manage operators.

### Deployment configuration

Add environment profiles:

```text
local
internal
production-like
test
```

Add/update:

```text
.env.example
docs/DEPLOYMENT_READINESS.md
docs/SECURITY_BOUNDARIES.md
docs/OPERATOR_UI_SECURITY.md
```

### Security controls

Add or verify CSRF on POST forms, path traversal protection, no raw token export, secure preview token hashing, SSRF guard for audits, no secrets in logs, safe error pages, and audit event coverage for sensitive UI actions.

### Health/readiness

Improve deployment checks for database connectivity, Redis connectivity, artifact storage configured, export root configured, demo artifact root configured, migrations current, and external sending disabled.

## Sprint 25 — Artifact Hosting / Storage Hardening

### Goals

Move toward durable artifact storage while preserving controlled preview safety.

### Storage abstraction

Add provider-neutral storage interface:

```text
ArtifactStorage
LocalArtifactStorage
ObjectStorageArtifactStorage placeholder or implementation
```

Support put artifact, get artifact, exists, generate internal path/ref, generate signed read URL if configured, and delete/revoke where appropriate. Listing is not required.

### Cloudflare R2/S3-compatible option

If practical, add optional S3-compatible storage configuration:

```text
LBOE_STORAGE_BACKEND=local|s3
LBOE_S3_ENDPOINT_URL=
LBOE_S3_BUCKET=
LBOE_S3_ACCESS_KEY_ID=
LBOE_S3_SECRET_ACCESS_KEY=
LBOE_S3_REGION=
LBOE_SIGNED_URL_TTL_SECONDS=
```

Do not commit credentials.

If implementation is too large, create the abstraction and docs with local backend only, leaving S3/R2 as a clearly documented placeholder.

### Artifact types

Cover audit screenshots, demo artifacts, export packs, and preview assets.

### Preview hosting hardening

Ensure external previews use token validation, the concept disclaimer is always visible, expired/revoked links are blocked, arbitrary file serving is impossible, signed URLs do not expose raw filesystem paths, and access events remain minimal.

### Retention policy

Add docs and optional metadata for audit artifact retention, demo preview retention, export retention, revoked preview handling, and closed pilot artifact handling.

Create/update:

```text
docs/ARTIFACT_STORAGE.md
docs/PREVIEW_HOSTING.md
docs/RETENTION_POLICY.md
```

## Tests

Add tests for login/logout, viewer cannot mutate, role restrictions, CSRF on mutating forms, configurable secure cookies, sensitive action audit events, no secrets in rendered pages/errors, readiness deployment checks, local artifact storage through abstraction, path traversal blocks, preview links not exposing raw paths, revoked/expired preview links blocked, export artifacts via storage abstraction where applicable, object storage config validation without credential leaks, retention docs, system_delivery_count = 0, and no sending/inbox/CRM integration.

## Validation commands

```powershell
ruff format --check .
ruff check .
mypy apps packages integrations tests
pytest
python scripts/verify_bootstrap.py
docker compose config
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL --reset-synthetic
python scripts/smoke_pilot_flow.py --base-url http://127.0.0.1:8000
python scripts/smoke_pilot_operations.py --base-url http://127.0.0.1:8000
```

If migrations are added:

```powershell
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

Add deployment/security smoke checks if feasible.

## Expected commits

```text
feat(security): harden internal deployment and operator auth
feat(storage): add durable artifact storage abstraction
```

## Completion report

Return summary by sprint, commit SHAs, migrations added, auth/session/CSRF changes, role enforcement changes, deployment profile changes, artifact storage changes, preview hosting hardening, tests run and results, seed/smoke results, known limitations, architectural deviations, confirmation that system_delivery_count remains 0, confirmation that no automated sending/inbox sync/CRM sync was added, and confirmation that Sprint 26 was not started.
