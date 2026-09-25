# Architecture Decisions — v0.1

## ADR-001 — The platform is source-agnostic

**Decision:** Discovery and enrichment sources are adapters.  
**Reason:** Avoid hard dependency on Google scraping or any single API.

## ADR-002 — Separate discovery and enrichment

**Decision:** Cheap discovery precedes richer enrichment.  
**Reason:** Control cost, latency and policy exposure.

## ADR-003 — Deterministic scoring

**Decision:** LLMs do not directly choose the numeric Opportunity Score.  
**Reason:** Explainability, testing and calibration.

## ADR-004 — Template-first demos

**Decision:** v0.1 uses controlled templates plus structured AI content.  
**Reason:** Higher reliability, lower cost, easier QA than unrestricted code generation.

## ADR-005 — Human approval before outreach

**Decision:** no autonomous outbound sending in v0.1.  
**Reason:** quality, consent and early-stage learning.

## ADR-006 — Provenance on every important fact

**Decision:** source, freshness, confidence and storage policy are first-class data.  
**Reason:** prevent factual drift and support source-policy compliance.

## ADR-007 — Postgres + Redis before workflow platforms

**Decision:** use simple queues for MVP.  
**Reason:** Temporal-class orchestration is valuable later but unnecessary before real workflow complexity appears.

## ADR-008 — Business-owned data is preferred for generated demos

**Decision:** facts used in demos should preferentially come from the business's own website or operator verification.  
**Reason:** reduces source-policy and factual-risk problems.

## ADR-009 — Score is opportunity, not business quality

**Decision:** labels and UI must avoid implying that a high score means the business itself is bad.  
**Reason:** the score measures addressable digital gap and delivery fit.

## ADR-010 — Lightweight audits may start from discovery

**Decision:** A homepage-only digital audit may transition a canonical
`DISCOVERED` business through `AUDITING` to `AUDITED`; the transition remains
recorded as a pipeline event. Deep enrichment is still a separate future
stage.
**Reason:** Sprint 2 discovery already stores a business-owned website, while
waiting for a future enrichment worker would prevent the objective baseline
audit. This edge is intentionally narrow and does not authorize scoring,
outreach, or transactional site actions.
