# AGENTS.md — Local Business Opportunity Engine

These instructions apply to all AI coding agents, including Codex CLI.

## 1. Mission

Build LBOE as a **local-business acquisition operating system**, not as a scraper script and not as a website generator. Preserve the pipeline:

`discover → normalize/dedupe → qualify → enrich → audit → score → intelligence → demo → QA → human review → offer/outreach draft → consent gate → CRM → learning`

## 2. Source of truth

Before modifying code, read in this order:

1. `docs/BLUEPRINT.md`
2. `docs/DECISIONS.md`
3. the current sprint file in `docs/`
4. `docs/MVP_BACKLOG.md`
5. relevant schemas/configs

When implementation and docs disagree, do **not** silently choose a different architecture. Either align the code or add an ADR-style note to `docs/DECISIONS.md` explaining the deviation.

## 3. Non-negotiable architecture rules

- Keep discovery, enrichment, audit, generation, and publishing providers behind adapters.
- PostgreSQL is the system of record for v0.1.
- Redis-backed workers are sufficient for v0.1; do not introduce Temporal/Celery/Kafka unless a sprint explicitly requires it.
- Numeric Opportunity Scores are deterministic and rules-based. LLMs may explain but must not arbitrarily set the score.
- Every important external fact carries provenance, confidence, observation time, and storage-policy metadata.
- Do not treat scraped/public contact data as permission for automated marketing.
- No automatic mass outreach in v0.1.
- Generated demos must be concept previews and must not imply affiliation or endorsement.
- Prefer business-owned sources for facts used in demos.
- Do not persist third-party API payloads indiscriminately.

## 4. Sprint discipline

Implement **only the active sprint** unless a tiny adjacent change is required to make the sprint coherent.

For Sprint 1, specifically do **not** implement:

- Google Maps scraping
- Google Places enrichment
- Playwright auditing
- LLM calls
- demo generation
- outbound email/WhatsApp sending
- production deployment

Stubs/interfaces are fine when needed to preserve contracts.

## 5. Engineering quality gates

Before declaring a task complete:

- run unit/integration tests relevant to the change
- run formatting/linting
- run static type checks
- run database migration checks if schema changed
- verify no secrets are committed
- verify docs reflect setup and behavior changes

Prefer small, testable modules and pure functions for domain logic.

## 6. Git discipline

- Make small, descriptive commits at stable milestones.
- Never force-push shared branches unless explicitly instructed.
- Never rewrite history to hide implementation problems.
- Do not commit `.env`, credentials, local DB volumes, prospect datasets, or generated private artifacts.
- Commit messages should describe intent, e.g. `feat(domain): add lead state transition guard`.

## 7. Data model rules

Use UUID primary identifiers unless a sprint explicitly says otherwise.

Core entities must preserve:

- business identity
- source observations/provenance
- pipeline events
- opportunity score version/components
- suppression/consent state
- jobs/idempotency metadata
- cost events when relevant

Every state transition must be auditable.

## 8. API rules

- Version public endpoints under `/v1`.
- Use explicit request/response models.
- Avoid leaking provider-specific payloads into domain responses.
- Return machine-readable validation errors.
- Keep health and readiness endpoints lightweight.

## 9. Security and privacy

- Secrets via environment variables or a secret manager only.
- No credentials in test fixtures.
- Avoid logging full third-party payloads or personal contact data by default.
- Add suppression/consent checks before any future send action.
- Treat Terms-of-Service and data-retention constraints as engineering requirements, not documentation footnotes.

## 10. Definition of done for agent work

When finishing a sprint/task, report:

1. completed requirements
2. files/modules added or changed
3. test/lint/typecheck results
4. migrations applied/validated
5. architectural deviations, if any
6. known limitations
7. next recommended work

Do not claim completion if validation is red.
