# Sprint 12 — Pilot Metrics and Reporting

Sprint 12 adds live deterministic pilot reports over the PostgreSQL system of
record. No dashboard, CRM sync, inbox sync, message sending, forecasting, or
LLM analysis is included.

Reports expose current funnel state counts, recorded state transitions,
discovery provenance and dedupe counts, audit health and finding counts,
score bands/actions, demo QA and review outcomes, outreach draft/readiness
metrics, manual execution channels, CRM event outcomes, operator workload,
suppression/hold counts, and failed or not-eligible jobs.

Use `GET /v1/reports/pilot` for a global report, optionally filtering by
`vertical`, `start_date`, `end_date`, and `include_details=true`. Use
`GET /v1/campaigns/{campaign_id}/reports/pilot` for a campaign-scoped report.
Date windows use record timestamps relevant to each table. Funnel counts are
current business states; transition and event metrics use append-only event
timestamps.

Manual outreach logs are operator assertions, so reports always expose a
system delivery count of zero. These metrics are suitable for a 10–50 lead
pilot: operators can compare stage conversion, workload, quality gates, and
blocked jobs without implying external delivery or causation.
