# Work Batch 1 — Sprint 19: Execute Batch 2 Pilot

## Current accepted baseline

```text
9871c078e713ef8c6b5706b38dcee2cbda203e4a
chore(pilot): prepare second-batch scale-up pack
```

Do not start Sprint 20.

## Goal

Execute the prepared Cape Town hair-salon Batch 2 pilot using the Sprint 18 scale-up pack. This is an operational sprint: run the 25-lead pilot, compare it with Sprint 16, capture evidence, and produce a clear outcome report.

## Pilot profile

Use:

```text
config/pilots/cape-town-hair-salons-batch-2.yaml
```

Initial scope:

```text
Vertical: hair_salon
Geography: Cape Town, South Africa
Target lead count: 25
Mode: dry_run first
Expansion: do not expand to 50 during Sprint 19 unless explicitly reviewed and approved
Outreach: manual only
System delivery: must remain 0
```

## Non-goals

Do not add automated sending, email/WhatsApp/SMS sending, Gmail/Outlook integration, CRM sync, inbox sync, payments, public SaaS deployment, new enrichment provider integration, a new demo template system, or Sprint 20 work.

## Required deliverables

Create:

```text
docs/SPRINT_19_BATCH_2_EXECUTION_LOG.md
docs/SPRINT_19_BATCH_2_REAL_PILOT_NOTES.md
docs/SPRINT_19_BATCH_2_OUTCOME_REPORT.md
```

Update:

```text
docs/PILOT_COMPARISON_TEMPLATE.md
```

The execution log must record campaign ID, pilot ID, source-policy acknowledgement, readiness result, discovery/import result, audit result, score/brief/demo result, QA result, preview/outreach-readiness result, export result, retrospective result, defects found, and fixes applied.

The notes document must include tables for lead intake, audit outcomes, score/brief/demo outcomes, preview/outreach readiness, manual outreach/CRM outcomes, and operator observations. Keep contact data minimal. Do not include secrets, raw preview tokens, raw scraper payloads, or private message transcripts.

The outcome report must include businesses discovered/imported, duplicates, ambiguous candidates, audit success/failure, score count and average, score bands, brief count, demo count, QA pass/fail, approved demos, preview links, outreach draft packages, readiness reviews, OUTREACH_READY leads, manual contacts, replies, meetings, proposals, wins/losses, system_delivery_count, operator friction, quality findings, and recommended Sprint 20–21 actions.

## Export pack verification

Generate and verify the Batch 2 export pack:

```text
pilot-summary.json
pilot-report.json
leads.csv
demo-links.csv
operator-activity.csv
```

Verify exports exclude raw preview tokens, secrets, credentials, raw scraper payloads, and unsupported sensitive inferred data.

## Execution sequence

1. Confirm baseline and working tree.
2. Start services.
3. Run migrations.
4. Run seed reset and smoke checks.
5. Open `/ui/pilots`.
6. Create Batch 2 from `config/pilots/cape-town-hair-salons-batch-2.yaml`.
7. Confirm active operator exists.
8. Acknowledge source policy.
9. Run readiness.
10. Keep pilot in dry-run until readiness passes.
11. Discover/import 25 real leads.
12. Review ambiguous and weak-evidence queues before demos.
13. Audit websites.
14. Score and brief all valid leads.
15. Generate demos only for eligible leads.
16. Review QA failures; never share failed artifacts.
17. Human-review demos.
18. Create expiring controlled preview links only for approved demos.
19. Generate outreach drafts and readiness reviews.
20. Manual outreach remains outside LBOE. Only log if actually performed.
21. Generate export pack.
22. Complete retrospective.
23. Fill comparison template.
24. Produce outcome report.

## Safety rules

```text
LBOE does not send messages.
Manual outreach happens outside LBOE.
Logging contact records only records operator assertions.
Concept previews are not official websites.
Preview tokens must not be stored raw or exported.
system_delivery_count must remain 0.
```

Stop immediately if system_delivery_count becomes non-zero, unexpected sending appears, preview tokens appear in export, raw scraper payload appears in export, more than 30% of demos fail QA, or operators cannot explain score/action reasoning.

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

If real-run fixes are added, include regression tests.

## Expected commit message

```text
chore(pilot): execute second controlled real pilot batch
```

## Completion report

Return summary, commit SHA, campaign ID, pilot ID, Batch 2 metrics, comparison vs Sprint 16, export verification, retrospective summary, defects found/fixed, validation results, known limitations, architectural deviations, confirmation that system_delivery_count remained 0, confirmation that no automated sending/inbox sync/CRM sync was added, and confirmation that Sprint 20 was not started.
