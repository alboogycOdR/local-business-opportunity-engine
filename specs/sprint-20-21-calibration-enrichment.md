# Work Batch 2 — Sprint 20–21: Calibration + Enrichment

## Current baseline

Start from the accepted Sprint 19 commit after Work Batch 1 is complete.

Do not start Sprint 22.

## Goal

Use Sprint 16 and Sprint 19 pilot evidence to improve LBOE's decision quality.

This batch has two parts:

```text
Sprint 20: Pilot outcome analysis and scoring/demo eligibility calibration
Sprint 21: Enrichment Layer v1
```

## Non-goals

Do not add automated sending, email/WhatsApp/SMS sending, Gmail/Outlook integration, CRM sync, inbox sync, payments, public SaaS deployment, autonomous prospecting, autonomous follow-ups, or Sprint 22 work.

## Sprint 20 — Calibration

### Goals

1. Compare Sprint 16 and Sprint 19 outcomes.
2. Identify scoring patterns that produced useful leads.
3. Identify weak-evidence and QA-failure patterns.
4. Improve calibration reporting and operator decision support.
5. Add regression coverage for calibration logic.

### Deliverables

Create or update:

```text
docs/SPRINT_20_CALIBRATION_REPORT.md
docs/SCORE_CALIBRATION_GUIDE.md
docs/DEMO_ELIGIBILITY_CALIBRATION.md
```

The calibration report should include Sprint 16 metrics, Sprint 19 metrics, score band comparison, demo generation rate, QA pass/fail comparison, approved-demo rate, OUTREACH_READY rate, manual-contact/reply/meeting outcomes if any, common high-scoring lead traits, common false-positive traits, common low-confidence traits, recommended score rule changes, recommended demo eligibility rule changes, and recommended QA rule changes.

### Product/API/UI improvements

Add or improve:

```text
pilot calibration page/table
score component explanation clarity
safe next-action explanation
demo eligibility explanation
QA failure explanation
weak-evidence reason labels
operator-visible source confidence
exported calibration summary
```

Possible UI routes:

```text
/ui/pilots/{pilot_id}/calibration
/ui/reports/calibration
```

If these already exist, extend them rather than duplicating.

### Scoring calibration

Do not radically change scoring without evidence. If changes are made, document old vs new behavior, include fixtures based on Sprint 16/19 patterns, keep deterministic scoring, and preserve holds such as SUPPRESSED, AMBIGUOUS_IDENTITY, NO_VERIFIABLE_CONTACT, and INSUFFICIENT_FACTS_FOR_DEMO.

Suggested improvements:

```text
clearer treatment of no-website leads
clearer treatment of healthy-site score_only leads
better confidence reduction for weak source identity
better evidence requirements for demo eligibility
better separation between technical-cleanup and full rebuild opportunities
```

## Sprint 21 — Enrichment Layer v1

### Goals

Add a safer enrichment layer that improves lead evidence without changing the outreach boundary. Initial enrichment should prefer business-owned or public website sources and normalize facts for scoring/brief/demo use.

### Enrichment model

Add provider-neutral enrichment contracts:

```text
EnrichmentRequest
EnrichmentResult
EnrichmentFact
EnrichmentEvidence
EnrichmentSource
EnrichmentConfidence
```

Each enrichment fact should capture business_id, source_type, source_url, fact_type, value, confidence, observed_at, evidence, and policy.

Suggested fact types:

```text
website_homepage
booking_link
whatsapp_link
email_address
phone_number
service_catalogue_present
price_list_present
location_page_present
social_link
business_owned_claim
third_party_claim
```

### Source policy

Distinguish business-owned website facts, public listing facts, third-party/social facts, and operator-entered facts. Business-owned facts should have higher confidence than third-party listing facts. Do not copy reviews into demos. Do not infer sensitive traits. Do not scrape broad social feeds.

### Adapters

Implement minimal deterministic/website enrichment if feasible:

```text
public website homepage enrichment
contact/action-link extraction
social-link extraction
booking-link extraction
service-signal extraction
```

If live web enrichment is too large, implement contracts, fake adapter, persistence, docs, and a minimal homepage parser for already-known website URLs. Do not add paid provider/API dependencies unless approved.

### Persistence

If needed, add migration:

```text
infrastructure/database/migrations/00XX_enrichment.sql
```

Suggested tables:

```text
enrichment_runs
enrichment_facts
enrichment_evidence
```

### API/UI

Add endpoints if aligned with current API style:

```text
POST /v1/businesses/{business_id}/enrich
GET  /v1/businesses/{business_id}/enrichments
GET  /v1/enrichments/{enrichment_id}
```

UI should add a lead-detail enrichment section, source confidence badges, enrichment evidence summary, and enrichment run status.

### Integration points

Enrichment should support scoring evidence, brief facts, demo eligibility, operator review, and calibration reports. It must not create outreach, send messages, or mark leads contacted.

## Tests

Add tests for calibration report metrics, score/demo eligibility explanations, weak-evidence reason labels, enrichment contract validation, fake enrichment adapter behavior, website enrichment extraction, append-only enrichment persistence, visible source confidence, scoring/brief integration without raw blobs, no copied reviews entering demo facts, no sending/inbox/CRM integration, and system_delivery_count remaining 0.

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

If a migration is added:

```powershell
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

## Expected commits

```text
feat(pilot): add outcome calibration reporting
feat(enrichment): add source-aware enrichment layer
```

## Completion report

Return summary by sprint, commit SHAs, migrations added, API/UI routes added, calibration findings, scoring/demo eligibility changes, enrichment model/adapters, tests run and results, seed/smoke results, known limitations, architectural deviations, confirmation that system_delivery_count remains 0, confirmation that no automated sending/inbox sync/CRM sync was added, and confirmation that Sprint 22 was not started.
