# Sprint 2 — Discovery, Normalization, and Deduplication

Sprint 2 adds a provider-neutral discovery contract, a separately packaged
Mahanaicoach scraper REST adapter, deterministic fake adapter, normalized
candidate handling, conservative identity matching, and idempotent discovery
jobs. It deliberately does not add Places enrichment, browser auditing,
scoring execution, AI, demos, outreach, or an operator UI.

Sprint 2.1 hardens the location contract (coordinates are explicit and
provider-neutral), scopes idempotency by campaign, migrates provider identities
into `business_external_identities`, and retains ambiguous candidates in
`discovery_candidates` for later operator resolution.

Run the API with the feature flag disabled by default. Use the fake adapter in
tests/local development; enable the maps adapter only for a small, deliberate
smoke test. Apply `infrastructure/database/migrations/0002_discovery.sql`
after the Sprint 1 migration when upgrading an existing database.
