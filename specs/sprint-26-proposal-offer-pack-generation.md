# Sprint 26 Codex CLI Handoff — Proposal / Offer Pack Generation

## Current accepted baseline

Repository:

```text
alboogycOdR/local-business-opportunity-engine
```

Current accepted baseline:

```text
a5e913b371bc668c4969f1b79fc31eedbeec1133
feat(storage): add durable artifact storage abstraction
```

Sprint 1–25 are accepted.

Do **not** start Sprint 27.

---

# 1. Goal

Build **Sprint 26: Proposal / Offer Pack Generation**.

LBOE can now discover, audit, score, brief, demo, review, enrich, draft outreach, track manual CRM events, run controlled pilots, and safely host artifacts/previews.

Sprint 26 should add the missing commercial bridge:

```text
interested/replied lead
→ reviewed proposal package
→ operator-approved offer pack
→ local export for manual use
```

This is not a sending, payment, contract, or e-signature sprint.

The proposal pack must be:

```text
deterministic
evidence-backed
operator-reviewed
safe to export locally
clearly marked as draft/proposal support
not legal advice
not an automatically sent document
```

---

# 2. Non-goals

Do **not** add:

```text
automated sending
email sending
WhatsApp API sending
SMS sending
Gmail/Outlook sending integration
inbox sync
CRM sync
payments
billing
contracts
e-signature
legal terms as final legal advice
autonomous negotiation
automatic follow-ups
public SaaS launch
Sprint 27 work
```

Manual communication remains outside LBOE.

`system_delivery_count` must remain `0`.

---

# 3. Product concept

Add a reviewed proposal workflow for businesses that have reached meaningful commercial interest.

Proposal packages should help an operator answer:

```text
What are we offering this business?
Why is this offer justified by evidence?
What is included?
What is excluded?
What assumptions are being made?
What information do we still need from the client?
What is the suggested next step?
```

The proposal package is an internal/operator artifact. It can be exported and manually shared outside LBOE by the operator, but LBOE must not send it.

---

# 4. Eligibility

A business should be eligible for proposal generation when at least one of these conditions is true:

```text
CRM event indicates reply_received with interested/asked_for_info/meeting_requested/proposal_requested
business lifecycle is REPLIED, MEETING, or PROPOSAL
operator manually marks proposal_requested
approved demo exists and outreach readiness/draft package exists
```

Proposal generation must be blocked if:

```text
business is suppressed
business has do_not_contact hold
identity is ambiguous
no sufficient evidence exists
demo/proposal claims would be unsupported
lead has no operator-entered interest signal
latest demo is QA failed and no approved demo exists
```

When blocked, return/display clear reason codes.

Suggested block reason codes:

```text
business_suppressed
do_not_contact
ambiguous_identity
insufficient_evidence
no_interest_signal
no_approved_demo
qa_failed_demo
missing_brief
missing_score
```

---

# 5. Proposal types

Support deterministic proposal/offer types:

```text
starter_website_build
website_refresh
conversion_upgrade
technical_cleanup
care_plan
custom_manual_scope
```

Selection logic should be based on existing brief, score, demo type, audit findings, enrichment facts, CRM interest, and operator input.

Examples:

```text
no verified website + approved starter demo → starter_website_build
healthy site + conversion gaps → conversion_upgrade
healthy site + technical findings → technical_cleanup
existing client-like interest + ongoing maintenance need → care_plan
operator-selected custom path → custom_manual_scope
```

Do not invent work scope unsupported by the available evidence.

---

# 6. Data model

Add migration:

```text
infrastructure/database/migrations/0018_proposals.sql
```

Suggested tables:

## proposal_packages

Fields:

```text
id UUID primary key
business_id UUID not null references businesses(id)
campaign_id UUID nullable references campaigns(id)
proposal_type text not null
status text not null
title text not null
summary text not null
recommended_next_step text not null
pricing_mode text not null
timeline_mode text not null
created_by_operator_id UUID nullable references operators(id)
source_brief_id UUID nullable
source_score_id UUID nullable
source_demo_id UUID nullable
source_outreach_draft_package_id UUID nullable
created_at timestamptz not null
updated_at timestamptz not null
approved_at timestamptz nullable
rejected_at timestamptz nullable
exported_at timestamptz nullable
```

Suggested statuses:

```text
draft
review_pending
approved
rejected
exported
archived
```

Suggested pricing modes:

```text
placeholder
operator_entered
not_included
```

Suggested timeline modes:

```text
placeholder
operator_entered
not_included
```

## proposal_sections

Fields:

```text
id UUID primary key
proposal_package_id UUID not null references proposal_packages(id)
section_type text not null
title text not null
body text not null
sort_order integer not null
evidence jsonb not null default '{}'
created_at timestamptz not null
```

Suggested section types:

```text
business_context
observed_opportunity
recommended_solution
deliverables
implementation_steps
assumptions
exclusions
client_questions
timeline
pricing_placeholder
next_step
```

## proposal_line_items

Fields:

```text
id UUID primary key
proposal_package_id UUID not null references proposal_packages(id)
item_type text not null
title text not null
description text not null
pricing_placeholder text nullable
timeline_placeholder text nullable
evidence jsonb not null default '{}'
sort_order integer not null
created_at timestamptz not null
```

Suggested item types:

```text
setup
design
content
technical_cleanup
conversion
hosting
maintenance
training
custom
```

## proposal_assumptions

Fields:

```text
id UUID primary key
proposal_package_id UUID not null references proposal_packages(id)
assumption_type text not null
body text not null
requires_client_confirmation boolean not null default true
created_at timestamptz not null
```

## proposal_review_events

Fields:

```text
id UUID primary key
proposal_package_id UUID not null references proposal_packages(id)
operator_id UUID nullable references operators(id)
decision text not null
note text not null default ''
created_at timestamptz not null
```

Suggested decisions:

```text
approve
reject
request_changes
mark_exported
archive
```

## proposal_exports

Fields:

```text
id UUID primary key
proposal_package_id UUID not null references proposal_packages(id)
status text not null
export_root text not null
files jsonb not null default '{}'
warnings jsonb not null default '[]'
created_by_operator_id UUID nullable references operators(id)
created_at timestamptz not null
```

Add indexes for:

```text
proposal_packages(business_id)
proposal_packages(status)
proposal_sections(proposal_package_id)
proposal_line_items(proposal_package_id)
proposal_review_events(proposal_package_id)
proposal_exports(proposal_package_id)
```

---

# 7. Contracts / models

Add provider-neutral proposal contracts.

Suggested Python contracts:

```text
ProposalGenerationRequest
ProposalPackageResult
ProposalSection
ProposalLineItem
ProposalAssumption
ProposalReviewRequest
ProposalReviewResult
ProposalExportResult
ProposalEvidenceRef
```

Proposal evidence references should support:

```text
source_type
source_id
code
description
confidence
```

Do not store raw scraper payloads or raw preview tokens as evidence.

---

# 8. Proposal generation service

Add deterministic service logic, for example:

```text
apps/api/src/lboe_api/proposal_service.py
```

Responsibilities:

```text
check eligibility
select proposal type
build proposal package
create sections
create line items
create assumptions
attach evidence refs
persist append-only proposal history
support review decisions
support local export
```

The service should pull from:

```text
business
contacts
latest score
latest brief
latest approved demo
latest outreach draft package
latest CRM events
audit findings
enrichment facts if available
operator input
```

## Required proposal sections

Each generated proposal should include at minimum:

```text
Business context
Observed opportunity
Recommended solution
Proposed deliverables
Assumptions
Exclusions
Client questions
Timeline placeholder
Pricing placeholder
Next step
```

## Pricing and timeline

Default behavior:

```text
Do not invent price.
Do not invent timeline.
Use placeholders unless operator provides values.
```

Examples:

```text
Pricing: "To be confirmed after scope review."
Timeline: "To be confirmed after content, access, and approval requirements are known."
```

If operator-entered values are supported, store them as operator-entered values and mark them clearly.

---

# 9. API changes

Add JSON API endpoints:

```text
POST /v1/businesses/{business_id}/proposal
GET  /v1/businesses/{business_id}/proposals
GET  /v1/proposals/{proposal_id}
POST /v1/proposals/{proposal_id}/review
POST /v1/proposals/{proposal_id}/export
GET  /v1/proposals/{proposal_id}/exports
```

Behavior:

## POST /v1/businesses/{business_id}/proposal

Creates a proposal package if eligible.

Request fields may include:

```text
proposal_type optional
pricing_mode optional
timeline_mode optional
operator_notes optional
idempotency_key optional
```

Should return:

```text
created proposal result
or ineligible result with reason codes
```

## POST /v1/proposals/{proposal_id}/review

Supports:

```text
approve
reject
request_changes
archive
```

Approval must require checklist-like safety checks, either explicit in request or enforced server-side.

## POST /v1/proposals/{proposal_id}/export

Creates local export artifacts.

Suggested export files:

```text
proposal-summary.json
proposal.md
proposal-sections.json
proposal-line-items.csv
proposal-evidence.json
```

Export must exclude:

```text
raw preview tokens
secrets
credentials
raw scraper payloads
unsupported sensitive inferred data
```

---

# 10. UI changes

Add operator UI routes:

```text
GET  /ui/businesses/{business_id}/proposal
POST /ui/businesses/{business_id}/proposal
GET  /ui/proposals/{proposal_id}
POST /ui/proposals/{proposal_id}/review
POST /ui/proposals/{proposal_id}/export
GET  /ui/proposals/{proposal_id}/exports
GET  /ui/queues/proposal-ready
```

## Lead detail page

Add a proposal section showing:

```text
latest proposal status
proposal type
approved/exported state
safe next action
link to proposal page
```

## Proposal page

Show:

```text
business identity
proposal status
proposal type
summary
sections
line items
assumptions
exclusions
client questions
evidence references
review history
export history
safety banner
```

Safety banner:

```text
This proposal pack is for operator review. LBOE does not send proposals, collect payments, create contracts, or provide legal advice.
```

## Proposal-ready queue

Queue should show businesses with interest signals but no approved proposal.

Columns:

```text
business name
state
latest CRM event
approved demo?
outreach draft?
recommended proposal type
blocking reason if not eligible
safe next action
```

---

# 11. Review and approval rules

Proposal approval should verify:

```text
business identity is not ambiguous
business is not suppressed
no do-not-contact hold
claims are evidence-backed
pricing is placeholder or operator-entered
timeline is placeholder or operator-entered
exclusions are visible
client questions are included
proposal is not described as a legal contract
proposal has not been sent by LBOE
```

Failed checks must block approval and provide reasons.

---

# 12. Export behavior

Proposal export should write local artifacts under configured export root, for example:

```text
exports/proposals/{proposal_id}/proposal.md
exports/proposals/{proposal_id}/proposal-summary.json
exports/proposals/{proposal_id}/proposal-sections.json
exports/proposals/{proposal_id}/proposal-line-items.csv
exports/proposals/{proposal_id}/proposal-evidence.json
```

Rules:

```text
No raw preview tokens.
No credentials.
No secrets.
No raw scraper payload dumps.
No unsupported sensitive inferred data.
No automatic sharing.
```

If artifact storage abstraction from Sprint 25 is available, use or respect it where appropriate. If not practical, use the existing export root safely and document the limitation.

---

# 13. Reporting integration

Add proposal metrics to pilot/global reporting where practical:

```text
proposal_packages_created
proposal_approved
proposal_exported
proposal_rejected
proposal_ready_queue_count
```

Do not overbuild analytics. Keep deterministic.

---

# 14. Documentation

Add/update:

```text
docs/PROPOSAL_WORKFLOW.md
docs/OFFER_PACK_GUIDE.md
docs/LIMITATIONS.md
docs/API_EXAMPLES.md
docs/OPERATOR_UI.md
README.md
```

Document:

```text
proposal eligibility
proposal types
review process
export process
safety boundaries
pricing/timeline placeholder policy
what proposal packs are not
```

---

# 15. Tests

Add tests for:

## Eligibility

```text
reply/meeting/proposal-request lead can generate proposal
suppressed business blocked
do_not_contact business blocked
ambiguous identity blocked
no interest signal blocked
missing evidence blocked
QA-failed/no-approved-demo path blocked where appropriate
```

## Generation

```text
proposal package persists
sections persist
line items persist
assumptions persist
evidence refs persist
pricing placeholder used by default
timeline placeholder used by default
no unsupported claims generated
```

## Review

```text
approval succeeds when checks pass
approval fails when required checks fail
request_changes persists event
reject persists event
review history is append-only
```

## Export

```text
proposal export creates expected files
export excludes raw preview tokens
export excludes secrets/credentials
export excludes raw scraper payloads
export records metadata
path traversal blocked
```

## UI

```text
proposal-ready queue returns 200
business proposal page returns 200
proposal detail page returns 200
review/export forms do not send anything
safety banner visible
```

## Regression

```text
system_delivery_count remains 0
no sending routes/buttons introduced
existing seed flow passes
existing pilot smoke flow passes
existing pilot operations smoke flow passes
auth smoke still passes if present
enrichment idempotency smoke still passes if present
```

---

# 16. Validation commands

Run:

```powershell
ruff format --check .
ruff check .
mypy apps packages integrations tests
pytest
python scripts/verify_bootstrap.py
docker compose config
```

If migration is added:

```powershell
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

Run existing smoke flows:

```powershell
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL --reset-synthetic
python scripts/smoke_pilot_flow.py --base-url http://127.0.0.1:8000
python scripts/smoke_pilot_operations.py --base-url http://127.0.0.1:8000
```

If available from prior sprints, also run:

```powershell
python scripts/smoke_enrichment.py --base-url http://127.0.0.1:8000
python scripts/smoke_auth.py --base-url http://127.0.0.1:8000
```

If smoke script names differ, use the existing script names in the repo.

---

# 17. Expected commit message

Use:

```text
feat(proposals): add reviewed proposal package workflow
```

If multiple commits are needed, suggested split:

```text
feat(proposals): add proposal package workflow
docs(proposals): document offer pack process
```

But prefer one focused feature commit if clean.

---

# 18. Completion report

After implementation, stop.

Do **not** start Sprint 27.

Return:

```text
summary
commit SHA
migrations added
database tables added
API routes added
UI routes added
proposal eligibility behavior
proposal types supported
review/approval behavior
export files generated
reporting metrics added
tests run and results
migration result
seed/smoke results
known limitations
architectural deviations
confirmation system_delivery_count remained 0
confirmation no automated sending was added
confirmation no inbox sync was added
confirmation no CRM sync was added
confirmation no payments/contracts/e-signature were added
confirmation Sprint 27 was not started
```
