# Work Batch 3 — Sprint 22–23: Demo Quality + Outreach Workflow

## Current baseline

Start from the accepted Sprint 20–21 commit after Work Batch 2 is complete.

Do not start Sprint 24.

## Goal

Improve demo quality and manual outreach operations using calibrated scoring/enrichment evidence.

This batch has two parts:

```text
Sprint 22: Demo quality, templates, QA, and regeneration/manual-edit workflow
Sprint 23: Manual outreach workflow hardening
```

The system must still not send messages.

## Non-goals

Do not add automated sending, email provider integration, WhatsApp API sending, SMS sending, Gmail/Outlook sending, inbox sync, CRM sync, payments, public SaaS deployment, autonomous follow-ups, or Sprint 24 work.

## Sprint 22 — Demo Quality

### Goals

1. Improve deterministic demos based on QA failures and pilot outcomes.
2. Add clearer QA failure explanations.
3. Improve safe regeneration/manual-edit workflow.
4. Expand templates only where evidence supports it.
5. Strengthen evidence-to-claim controls.

### Deliverables

Create/update:

```text
docs/SPRINT_22_DEMO_QUALITY_REPORT.md
docs/DEMO_TEMPLATE_GUIDE.md
docs/DEMO_QA_GUIDE.md
docs/DEMO_REGENERATION_POLICY.md
```

### Template improvements

Improve existing template behavior before creating many new templates.

Possible template tracks:

```text
hair_salon_starter
hair_salon_conversion_upgrade
hair_salon_technical_cleanup
```

Rules:

```text
Do not invent prices.
Do not invent testimonials.
Do not claim official affiliation.
Do not copy reviews.
Do not make unsupported awards/quality claims.
Every claim must map to evidence.
Concept banner must remain visible.
```

### QA improvements

Add richer QA output:

```text
failed check code
human-readable explanation
severity
recommended fix
whether regeneration is allowed
whether manual edit is required
whether sharing is blocked
```

QA failure examples include missing concept disclaimer, unsupported claim, fake price/testimonial, external form/tracking script, official-site implication, insufficient evidence, and missing artifact.

### Regeneration/manual edit workflow

Add or improve request regeneration reason, manual edit required state, operator note, QA rerun after regeneration/manual edit, audit event, and history of attempts. Do not silently overwrite demos. Preserve history.

### Demo preview

Preview should show template type, QA status, evidence summary, claim count, and blocked sharing reason if failed.

## Sprint 23 — Manual Outreach Workflow

### Goals

Make manual outreach more usable without sending from LBOE.

### Features

Add/improve:

```text
copy-to-clipboard draft UI
manual contact checklist
call script view
WhatsApp manual copy view
email manual copy view
follow-up reminder records as local UI list only
objection logging
reply classification
next manual action
operator notes and audit events
```

LBOE may help the operator copy text or record actions, but it must not send messages.

### Outreach draft improvements

Improve draft package display with subject/preview, channel tabs, copyable text, evidence behind opportunity claim, do-not-send safety banner, and operator checklist.

### Manual follow-up records

Add a lightweight model if needed:

```text
manual_follow_up_tasks
```

Fields should include business_id, operator_id, reason, due_at, status, created_at, and completed_at. This should not send reminders automatically unless explicitly implemented as a local UI list only.

### Reply classification

Operator-entered classifications:

```text
interested
not_interested
asked_for_info
wrong_contact
do_not_contact
meeting_requested
proposal_requested
no_response_note
```

Update CRM event capture or add classification fields if needed.

### Objection logging

Operator-entered objections:

```text
too_expensive
already_has_provider
not_interested
call_later
wants_whatsapp
wants_email
needs_owner
other
```

These should feed reporting and retrospective.

## UI

Add/improve pages:

```text
/ui/queues/follow-up
/ui/businesses/{id}/outreach-workbench
/ui/businesses/{id}/demo-quality
/ui/demos/{id}/qa
/ui/demos/{id}/regenerate
```

Use simpler routes if consistent with current UI.

## Tests

Add tests for QA explanations, failed demo sharing blocks, regeneration history preservation, manual edit required state, copy-to-clipboard UI with no sending forms, outreach workbench safety banner, manual follow-up records, reply classifications, objection logs, reporting counts, system_delivery_count = 0, and absence of provider calls.

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

If migrations are added:

```powershell
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

## Expected commits

```text
feat(demo): improve QA explanations and regeneration workflow
feat(outreach): harden manual outreach workbench
```

## Completion report

Return summary by sprint, commit SHAs, migrations added, UI/API routes added, demo QA improvements, template changes, regeneration/manual edit behavior, manual outreach workflow changes, tests run and results, seed/smoke results, known limitations, architectural deviations, confirmation that system_delivery_count remains 0, confirmation that no automated sending/inbox sync/CRM sync was added, and confirmation that Sprint 24 was not started.
