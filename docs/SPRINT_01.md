# Sprint 1 — Foundation, Domain Core, and Manual Ingest

## Objective

Create the smallest dependable platform foundation on which discovery, auditing, enrichment, scoring, and demo generation can later be added without architectural rework.

## Scope

### A. Repository/tooling

- Establish coherent Python packaging for API, worker, domain, and scoring modules.
- Add root developer commands or scripts for install, test, lint, typecheck, and local services.
- Keep the operator web app as a documented placeholder only; no full UI required in Sprint 1.

### B. Local infrastructure

- PostgreSQL service.
- Redis service.
- Docker Compose local/dev configuration.
- Health checks for dependencies where reasonable.
- `.env.example` with safe defaults/placeholders.

### C. API

Build a FastAPI application with:

- `GET /health`
- `GET /ready`
- `POST /v1/campaigns`
- `GET /v1/campaigns/{id}`
- `GET /v1/businesses`
- `GET /v1/businesses/{id}`
- manual import endpoint or CLI for JSON/CSV candidates

Do not implement discovery provider calls yet.

### D. Domain/data model

At minimum implement:

- `campaigns`
- `businesses`
- `business_aliases` if needed for dedupe-ready identity
- `source_observations`
- `contacts` if useful for normalized imports
- `suppression_entries`
- `pipeline_events`
- `jobs`

Every business has a current pipeline state. Every state transition creates a `pipeline_event`.

### E. Lead state machine

Implement and test authoritative transition guards for at least:

`DISCOVERED → DEDUPED → QUALIFIED → ENRICHING → ENRICHED → AUDITING → AUDITED → SCORED → DEMO_QUEUED → DEMO_GENERATED → REVIEW_PENDING → APPROVED_FOR_OUTREACH → CONSENT_PENDING → OUTREACH_READY → CONTACTED → REPLIED → MEETING → PROPOSAL → WON/LOST`

Also support terminal/hold-style transitions such as `REJECTED`, `ARCHIVED`, `SUPPRESSED`, and `ENRICHMENT_FAILED` where defined in the blueprint.

Sprint 1 only needs the transition engine and persistence/audit trail; later services will drive many of these transitions.

### F. Provenance

For external/manual facts, store enough metadata to identify:

- field or subject
- source type
- source reference
- observed timestamp
- expiry timestamp if any
- storage policy (`persistent`, `ephemeral`, `reference_only`)
- confidence

Do not require a large raw provider payload to be stored.

### G. Manual ingest

Support JSON and CSV candidate import into a campaign.

Minimum accepted fields:

- display name
- category
- locality/address text
- source/source URL or reference when available
- phone/website flags or values when available

Import behavior:

- validate rows
- create source observation/provenance
- avoid obvious exact duplicates
- return per-row success/failure summary
- leave fuzzy dedupe for Sprint 2 unless simple normalization is trivial

### H. Tests

Include:

- state transition unit tests
- campaign CRUD/API tests
- manual import tests
- provenance persistence tests
- suppression tests
- health/readiness tests
- migration smoke test

### I. CI

On push/PR, run:

- formatter/lint check
- static type check
- tests

A service-container Postgres may be used for integration tests.

## Acceptance criteria

Sprint 1 is complete only when:

- [ ] a developer can start PostgreSQL and Redis locally using documented commands
- [ ] the API boots with environment-based configuration
- [ ] `/health` returns success when the process is alive
- [ ] `/ready` reflects required dependency availability
- [ ] database migrations create the Sprint 1 schema from empty state
- [ ] campaigns can be created/read
- [ ] businesses can be imported manually from CSV and JSON
- [ ] every imported business has source/provenance metadata
- [ ] exact duplicate protection exists for the chosen Sprint 1 identity key(s)
- [ ] lead state transitions are guarded and recorded as pipeline events
- [ ] suppression can be recorded and queried
- [ ] tests pass
- [ ] lint/format checks pass
- [ ] type checks pass
- [ ] CI config exists
- [ ] README contains tested setup instructions
- [ ] no secrets or prospect datasets are committed

## Stop condition

When all acceptance criteria pass, **stop**. Do not begin Maps discovery or website auditing in this sprint.
