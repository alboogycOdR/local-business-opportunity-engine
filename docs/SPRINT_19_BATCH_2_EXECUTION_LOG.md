# Sprint 19 — Batch 2 execution log

## Run identity

- Campaign: `Cape Town Hair Salons Pilot - Batch 2`
- Campaign ID: `760267fc-80f0-4dab-8a0a-cc2506bb5865`
- Pilot ID: `f3476c7d-8fe4-48b5-8f7d-4438277005d1`
- Date: 2026-09-28 (Africa/Johannesburg)
- Profile: `config/pilots/cape-town-hair-salons-batch-2.yaml`
- Mode: dry run
- Source policy: `pilot-source-v1`, acknowledged by `batch2-operator`
- System delivery count: **0**

## Execution record

| Gate | Result |
|---|---|
| Services / migrations | PostgreSQL, Redis, local API, and `gosom/google-maps-scraper:latest` available; migrations current |
| Readiness | Passed after active operator and source-policy acknowledgement were present |
| Discovery | One local-scraper job; 22 candidates returned, 21 imported, 1 duplicate, 0 ambiguous |
| Audit | 21 businesses processed; five initial attempts failed because the runner had already moved leads to `AUDITING`; retried through the existing audit path successfully. Findings include 18 healthy sites, 3 HTTP errors, and 1 TLS failure. |
| Score / brief | 21 scores and 21 briefs persisted; average score 61.86; bands 8 high / 2 medium / 11 low |
| Demo / QA | 4 demos generated for eligible no-website leads; 3 QA passed and were approved, 1 QA failed and was not shared |
| Preview / readiness | 3 seven-day controlled preview links created for approved demos; 3 draft packages and 3 consent-pending readiness reviews |
| Manual outreach / CRM | None performed; no contact, reply, meeting, proposal, win, or loss recorded |
| Export | `pilot-summary.json`, `pilot-report.json`, `leads.csv`, `demo-links.csv`, and `operator-activity.csv` generated and checked |
| Retrospective | Saved to the pilot record with operator friction and next-batch recommendations |

## Defects and fixes

No product-code defect was required for the successful retry. The first audit pass exposed an operational sequencing issue: callers must leave a lead in `ENRICHED` and let the audit service own the `ENRICHED → AUDITING → AUDITED` transition. The affected leads were recovered with explicit auditable transitions and retried once. No architecture change was made.

## Safety stop checks

- No automated email, WhatsApp, SMS, inbox, CRM, or payment integration was used.
- Preview tokens were not stored in this log or exported.
- Raw scraper payloads were not exported.
- QA-failed demo sharing was blocked.
- `system_delivery_count` remained `0`.
