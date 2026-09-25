# MVP Backlog — Buildable v0.1

This backlog assumes a single vertical pilot and 20–50 prospects.

## Epic 0 — Project foundation

- [ ] Create monorepo
- [ ] Add `.env.example`
- [ ] Add dev Docker Compose
- [ ] Add migrations
- [ ] Add CI: lint, typecheck, tests
- [ ] Add structured logging

**Done when:** a new developer can boot API, database, Redis and web UI with one documented command.

## Epic 1 — Campaigns and business records

- [ ] Campaign CRUD
- [ ] Business CRUD/read model
- [ ] Source observation/provenance model
- [ ] Contact model
- [ ] Pipeline events
- [ ] Suppression entries

**Done when:** every fact can be traced to a source observation.

## Epic 2 — Discovery

- [ ] Define `DiscoveryAdapter`
- [ ] Manual CSV adapter
- [ ] Google Maps scraper-kit adapter behind feature flag
- [ ] Job polling/timeout/retry
- [ ] Candidate normalization
- [ ] Exact + fuzzy dedupe
- [ ] Duplicate resolution screen

**Done when:** one campaign can ingest 20–50 candidates without duplicates entering the active pipeline.

## Epic 3 — Website resolver + audit

- [ ] Check website existence
- [ ] DNS/TLS/HTTP health
- [ ] Screenshot desktop/mobile
- [ ] Detect mobile viewport/overflow
- [ ] Detect click-to-call
- [ ] Detect WhatsApp
- [ ] Detect booking/reservation providers
- [ ] Detect forms
- [ ] SEO basics
- [ ] Accessibility baseline
- [ ] Store findings as structured records

**Done when:** operator sees objective evidence for each digital gap.

## Epic 4 — Opportunity score

- [ ] YAML score policy loader
- [ ] Deterministic scoring function
- [ ] Component explanation
- [ ] Hard holds
- [ ] Versioned score record
- [ ] Unit tests for every rule

**Done when:** same inputs + same policy version always produce the same score.

## Epic 5 — Enrichment

- [ ] Define `EnrichmentAdapter`
- [ ] Source-policy metadata
- [ ] Places reference adapter with field masks
- [ ] Business-owned site extractor
- [ ] Freshness/expiry handling
- [ ] Ephemeral field handling

**Done when:** the system can enrich a lead without indiscriminately storing restricted source content.

## Epic 6 — Business intelligence

- [ ] `BusinessBrief` JSON schema
- [ ] Prompt + model abstraction
- [ ] JSON-schema validation
- [ ] Provenance attachment to claims
- [ ] Retry/repair invalid outputs
- [ ] Human edit capability

**Done when:** no free-form model output is accepted as a business brief without schema validation.

## Epic 7 — Demo generator

- [ ] First vertical template
- [ ] Design tokens
- [ ] Structured page content schema
- [ ] Renderer
- [ ] Concept-preview banner
- [ ] Preview slug/domain strategy
- [ ] Static deployment adapter
- [ ] Generated asset manifest

**Done when:** a prospect can receive a functioning mobile-friendly preview URL.

## Epic 8 — Demo QA

- [ ] Browser smoke test
- [ ] Link/CTA test
- [ ] Placeholder leakage test
- [ ] Unsupported-claim test
- [ ] Mobile screenshot diff/manual inspection
- [ ] QA status + reasons

**Done when:** demos with blocking faults cannot be approved.

## Epic 9 — Offer builder

- [ ] Capability catalog
- [ ] Offer-rule engine
- [ ] Package templates
- [ ] Editable scope
- [ ] No hardcoded pricing in core engine

**Done when:** operator gets a reasoned offer derived from detected gaps.

## Epic 10 — Outreach/CRM

- [ ] Outreach draft schema
- [ ] Consent state
- [ ] Suppression check
- [ ] Human approval
- [ ] Manual send recording
- [ ] Reply/meeting/proposal/won/lost statuses
- [ ] Timeline

**Done when:** no lead can be marked “ready to contact” while suppressed or failing campaign policy.

## Epic 11 — Analytics

- [ ] Funnel counts
- [ ] Conversion by score band
- [ ] Conversion by gap type
- [ ] Cost ledger
- [ ] Processing error rate
- [ ] Demo regeneration rate

**Done when:** the pilot can answer whether the score and offer logic correlate with real outcomes.

## Suggested sprint sequence

### Sprint 1
Foundation, schema, campaigns, manual import, pipeline events.

### Sprint 2
Discovery adapter + dedupe + operator list.

### Sprint 3
Website audit + screenshots + deterministic findings.

### Sprint 4
Opportunity score + score explanation UI.

### Sprint 5
Enrichment + business brief.

### Sprint 6
Template demo + deploy + QA.

### Sprint 7
Offer/outreach draft + suppression/consent + CRM timeline.

### Sprint 8
Pilot run with 20–50 businesses, bug fixes, score calibration.

