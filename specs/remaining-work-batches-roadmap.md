# Remaining Work Batches Roadmap — LBOE

## Current accepted baseline

Repository:

```text
alboogycOdR/local-business-opportunity-engine
```

Current accepted baseline:

```text
9871c078e713ef8c6b5706b38dcee2cbda203e4a
chore(pilot): prepare second-batch scale-up pack
```

## Purpose

This roadmap groups the next major LBOE work into larger Codex CLI batches so implementation can proceed with fewer handoff cycles while preserving safety, reviewability, and clean commit boundaries.

## Batch sequence

| Work batch | Sprint scope | Theme | Primary outcome |
|---|---:|---|---|
| Work Batch 1 | Sprint 19 | Execute Batch 2 Pilot | Run the prepared 25-lead pilot and produce evidence |
| Work Batch 2 | Sprint 20–21 | Calibration + Enrichment | Improve scoring, eligibility, and evidence quality from real outcomes |
| Work Batch 3 | Sprint 22–23 | Demo Quality + Outreach Workflow | Improve demos and manual outreach operations without sending |
| Work Batch 4 | Sprint 24–25 | Deployment + Artifact Hosting Hardening | Prepare safer non-local operation and durable artifact storage |

## Global safety boundary

Across all batches:

```text
No automated sending.
No inbox sync.
No CRM sync.
No WhatsApp API sending.
No Gmail/Outlook sending integration.
No SMS sending.
No payments.
No autonomous outreach.
No raw preview tokens in exports.
No raw scraped payload resale.
system_delivery_count must remain 0 unless a future explicitly approved sending sprint changes the boundary.
```

Manual outreach, when performed, must happen outside LBOE. LBOE may record operator assertions, drafts, readiness decisions, preview links, exports, and retrospectives.

## Recommended execution model

Use one Markdown handoff per work batch. Run the batches in order. Later batch specs are intentionally strong first drafts, but should be reviewed after each completed batch because real pilot evidence may shift priorities.

## Commit discipline

Each combined work batch should create clean commits by sprint area:

```text
Sprint 19: one commit for Batch 2 execution documentation/results and any tiny fixes
Sprint 20: one commit for calibration/reporting/scoring improvements
Sprint 21: one commit for enrichment contracts/adapters
Sprint 22: one commit for demo quality improvements
Sprint 23: one commit for manual outreach workflow hardening
Sprint 24: one commit for deployment/security hardening
Sprint 25: one commit for artifact hosting/storage hardening
```

## Review checkpoint after each batch

After each batch, return:

```text
summary
commit SHA(s)
files added/updated
tests run and results
smoke results
pilot/report/export results where applicable
known limitations
architectural deviations
confirmation no prohibited integrations were added
confirmation next sprint/batch was not started
```
