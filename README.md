# Local Business Opportunity Engine (LBOE)

A controlled, measurable system for discovering local businesses, auditing their digital presence, scoring addressable opportunities, generating truthful demo experiences, and supporting human-approved sales workflows.

> **Status:** Sprint 2 discovery foundation implemented. External providers remain disabled by default.

## Product thesis

LBOE is **not** a Google Maps scraper and **not** an AI website builder. It is a local-business acquisition operating system built around a **show-before-sell** workflow:

```text
Discover → Normalize/Dedupe → Qualify → Enrich → Audit → Score
→ Business Intelligence → Demo → QA → Human Review
→ Offer/Outreach Draft → Consent Gate → CRM → Learning
```

## Architecture principles

- **Adapter-first:** external data sources are replaceable integrations, never the core domain.
- **Cheap-first funnel:** expensive enrichment and generation happen only after qualification.
- **Structured AI:** typed inputs/outputs and provenance instead of unstructured prompt dumps.
- **Explainable scoring:** every score stores its components and evidence.
- **Human-controlled irreversible actions:** no autonomous cold outreach in v0.1.
- **Source-policy-aware storage:** do not persist third-party data blindly.
- **Pilot before scale:** validate on 20–50 businesses before adding heavy automation.

## Repository map

```text
apps/
  api/              FastAPI core
  operator-web/     Operator console
  worker/           Background jobs
packages/
  domain/           Core domain/state machine
  schemas/          Shared JSON contracts
  scoring/          Deterministic opportunity scoring
  ai/               Structured AI contracts/prompts
integrations/
  maps-scraper/     Discovery adapter
  google-places/    Deep enrichment adapter
  website-auditor/  Browser/technical audit adapter
  demo-publisher/   Preview deployment adapter
infrastructure/
  database/         SQL migrations
  docker/           Local infrastructure
workflows/          Job/workflow definitions
config/             Scoring and vertical policies
tests/              Cross-package test suites
docs/               Product/architecture source of truth
```

## Read first

1. [`AGENTS.md`](./AGENTS.md) — engineering rules for Codex/agents.
2. [`docs/BLUEPRINT.md`](./docs/BLUEPRINT.md) — canonical product/system architecture.
3. [`docs/DECISIONS.md`](./docs/DECISIONS.md) — architectural decisions and postponed choices.
4. [`docs/SPRINT_01.md`](./docs/SPRINT_01.md) — first implementation milestone.
5. [`CODEX_KICKOFF.md`](./CODEX_KICKOFF.md) — exact first handoff instructions for Codex CLI.

## Reference projects

The architecture draws on two reference implementations, but neither owns the LBOE domain:

- `Mahanaicoach/google-maps-scraper-kit` — high-volume discovery reference.
- `deonna/google-maps-downloader` — Google Places API enrichment/structured business brief reference.

Their code, licenses, source terms, and external platform policies must be reviewed before copying or integrating implementation code.

## Current build boundary

The repository bootstrap defines the architecture. **Sprint 1** establishes the monorepo, FastAPI core, PostgreSQL, Redis, migrations, campaign/business/provenance models, lead state machine, manual lead import, tests, lint/type checking, and developer documentation.

Sprint 2 adds a provider-neutral discovery adapter and conservative normalization/dedupe. Maps scraping remains disabled by default and is never permission for outreach. Places enrichment, browser auditing, scoring execution, AI demo generation, automated outreach, and production deployment remain out of scope.

## Local bootstrap target

Local Sprint 1 setup (PowerShell or a Unix shell):

```bash
docker compose up -d postgres redis
python -m venv .venv
# activate .venv
pip install -e .
pytest
```

Start dependencies with `docker compose up -d postgres redis`, then run the API with
`uvicorn lboe_api.main:app --reload`. Copy `.env.example` to `.env` only when you
need local overrides. Apply `infrastructure/database/migrations/0001_initial.sql`
to PostgreSQL with `psql`; the API also creates the same tables on startup for a
fresh local/test database. Readiness requires both PostgreSQL and Redis; health is
process-only.

Manual import uses `POST /v1/campaigns/{campaign_id}/import` with either
`{"format":"json","records":[...]}` or `{"format":"csv","csv_text":"..."}`.
The endpoint records provenance, contacts, an initial `DISCOVERED` event, and
rejects exact duplicates within the campaign.

Discovery uses `POST /v1/campaigns/{campaign_id}/discover` with a body such as
`{"queries":["cafes"],"max_results":5,"idempotency_key":"pilot-1"}`. The
route invokes the configured `DiscoveryAdapter`, persists a `DISCOVER_CAMPAIGN`
job, and returns the same job/result for repeated idempotent requests. Identity
matching is conservative: source ID, trustworthy phone, normalized domain, and
name plus locality/address. Conflicting matches are recorded as ambiguous and
are not auto-merged.

Codex may refine this as long as the resulting workflow is documented and consistent with the architecture.

## Security

Never commit credentials, API keys, scraped datasets, prospect exports, generated private demos, or local `.env` files.
