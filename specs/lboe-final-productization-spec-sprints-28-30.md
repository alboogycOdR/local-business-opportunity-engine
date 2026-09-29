# LBOE Final Productization Specification

## Sprint 28–30 Codex CLI Handoff

**Project:** Local Business Opportunity Engine  
**Repository:** `alboogycOdR/local-business-opportunity-engine`  
**Current accepted baseline:** `d77c835` — `feat(delivery): expose operator delivery actions`  
**Phase:** Final Productization  
**Scope:** Sprint 28, Sprint 29, Sprint 30  
**Goal:** Move LBOE from a functionally complete platform into a polished, operable, deployable commercial v1.

---

## 0. Executive Summary

LBOE has now reached the end of its core platform build phase.

The system already supports:

```text
Discovery
→ Dedupe
→ Website audit
→ Opportunity scoring
→ Business intelligence brief
→ Enrichment
→ Demo generation
→ Demo QA
→ Human review
→ Controlled preview hosting
→ Outreach drafts
→ Outreach readiness
→ Manual outreach logging
→ CRM tracking
→ Pilot operations
→ Reporting
→ Proposal packs
→ Delivery project workflow
```

The final three sprints should **not** add large new business domains.

They should turn the platform into a usable, reliable, commercially credible v1.

The final roadmap is:

```text
Sprint 28:
Operator Experience + Production Operations

Sprint 29:
Production Deployment + Real-world Operations

Sprint 30:
Commercial Release Candidate + Final UX Polish + Documentation + Acceptance Testing
```

By the end of Sprint 30, the milestone statement should be:

```text
LBOE v1 is build-complete and ready to move from build mode into operate, sell, support, and evidence-driven iteration mode.
```

---

## 1. Global Safety Boundary

The following remain prohibited throughout Sprints 28–30 unless a future product-owner decision explicitly changes the scope:

```text
automated email sending
WhatsApp API sending
SMS sending
Gmail/Outlook sending integration
inbox sync
CRM sync
payments
billing
contracts
e-signature
autonomous outreach
autonomous follow-ups
domain purchasing
automated production website deployment
credential storage
raw preview token export
raw scraper payload resale
unsupported sensitive inferences
```

Manual outreach remains outside LBOE.

LBOE may:

```text
prepare drafts
support copy-to-clipboard
record operator assertions
record manual CRM events
generate proposal packs
manage delivery checklists
export local artifacts
show controlled preview links
```

LBOE must not:

```text
send messages
collect money
sign contracts
store credentials
claim legal approval
claim official business affiliation
```

`system_delivery_count` must remain `0`.

---

## 2. Global Engineering Rules

For every sprint:

1. Start from the accepted baseline.
2. Read this specification fully before implementation.
3. Make a short implementation plan.
4. Keep changes inside the sprint scope.
5. Preserve all prior workflows and safety gates.
6. Run the validation commands.
7. Commit with the expected commit message.
8. Push to `origin main`.
9. Report results and stop at the defined boundary.

Do **not** start the next sprint unless the current sprint is complete, committed, pushed, and validated.

If using automatic continuation, proceed only if all validation passes and no stop condition is triggered.

---

## 3. Stop Conditions

Stop and report immediately if any of the following occurs:

```text
pytest fails and cannot be fixed cleanly
mypy fails and cannot be fixed cleanly
ruff fails and cannot be fixed cleanly
migration fails
smoke flow fails
git push fails
merge conflict occurs
a requested feature would violate safety boundaries
a change requires storing credentials
a change implies automated sending
a change implies payments/contracts/e-signature
a production deployment action requires secrets that are not available
a spec is ambiguous enough to require product-owner approval
```

---

## 4. Required Validation Commands

Run the standard validation before every sprint commit:

```powershell
ruff format --check .
ruff check .
mypy apps packages integrations tests
pytest
python scripts/verify_bootstrap.py
docker compose config
```

If migrations were added or touched:

```powershell
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

Run existing smoke flows when the API is available:

```powershell
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL --reset-synthetic
python scripts/smoke_pilot_flow.py --base-url http://127.0.0.1:8000
python scripts/smoke_pilot_operations.py --base-url http://127.0.0.1:8000
```

Also run these if present:

```powershell
python scripts/smoke_proposals.py --base-url http://127.0.0.1:8000
python scripts/smoke_enrichment.py --base-url http://127.0.0.1:8000
python scripts/smoke_auth.py --base-url http://127.0.0.1:8000
```

After Sprint 27, also add or run delivery smoke coverage where available.


---

# Sprint 28 — Operator Experience + Production Operations

## 5. Sprint 28 Goal

Sprint 28 should answer this question:

```text
If a new operator joined tomorrow, could they become productive in one afternoon without needing a developer?
```

This is primarily an **Operator Experience** and **Production Operations** sprint.

It should polish the web UI into a coherent internal product, not add new business workflows.

---

## 6. Sprint 28 Product Principles

### 6.1 Operator-first

The operator should always understand:

```text
where they are
what this record is
why this item needs attention
what the recommended next action is
what is blocked
what is unsafe
what happens if they click a button
```

### 6.2 Guided workflow

The UI should guide the operator through the value chain:

```text
Campaign
→ Lead
→ Audit
→ Score
→ Brief
→ Demo
→ Review
→ Outreach
→ CRM
→ Proposal
→ Delivery
```

### 6.3 Fewer dead ends

Every page should provide at least one of:

```text
safe next action
reason no action is available
link to relevant queue
link to parent campaign/pilot
link to relevant artifact
```

### 6.4 No hidden sending

Every area involving outreach, proposal, or delivery must clearly state:

```text
LBOE does not send messages.
Manual communication happens outside LBOE.
```

---

## 7. Sprint 28 Scope

Sprint 28 includes:

```text
operator dashboard redesign
navigation/sidebar polish
lead detail page restructuring
queue usability improvements
global search or quick lookup
production operations dashboard
system health/status view
configuration/status visibility
admin/operator management polish
empty states
success/error messaging
onboarding/help copy
basic accessibility improvements
```

Sprint 28 does **not** include:

```text
new core business domains
new enrichment providers
automated sending
payments
contracts
public SaaS frontend rewrite
React/Next.js migration unless absolutely necessary
```

---

## 8. Sprint 28 UI Improvements

### 8.1 Main dashboard

Improve `/ui` so it functions as a daily operator home.

Suggested dashboard sections:

```text
Today’s priorities
Pilot health
Queue counts
Blocked items
Recent activity
System safety status
Production operations status
```

Example priority cards:

```text
Demos needing review
QA-failed demos
Weak-evidence leads
Proposal-ready leads
Delivery projects blocked
Follow-ups due
Pilots needing readiness
```

Each card should link directly to the relevant queue.

### 8.2 Navigation

Add or improve consistent navigation across the UI.

Suggested top-level sections:

```text
Dashboard
Campaigns
Queues
Pilots
Businesses
Proposals
Delivery
Reports
Admin
System
```

Every page should have:

```text
breadcrumb
page title
primary action
secondary actions
back link
```

### 8.3 Lead detail page

The business/lead detail page is likely too long. Reorganize it into clear sections.

Preferred structure:

```text
Overview
Evidence
Score
Audit
Brief
Demo
Outreach
CRM
Proposal
Delivery
History
```

If tabs are too much, use anchored sections with clear headings and a sticky summary.

The top summary should show:

```text
business name
lifecycle state
score/band
recommended action
current block reason, if any
safe next action
active pilot/campaign
assigned operator
```

### 8.4 Queues

Improve queues to make operator work easier.

Required queue improvements:

```text
clear descriptions
counts
sort by age/priority
safe next action
blocking reason
links to lead detail
empty-state text
```

Important queues:

```text
Needs audit
Needs score
Weak evidence
No demo reason
QA failed
Needs demo review
Not outreach-ready
Proposal-ready
Delivery blocked
Follow-up due
```

### 8.5 Proposal and delivery UX

Proposal and delivery pages should show:

```text
status
next action
blocking reason
safety boundary
export status
review/approval history
```

The proposal page must make clear:

```text
Proposal pack is not a contract.
LBOE does not send proposals.
LBOE does not collect payment.
```

The delivery page must make clear:

```text
Do not store credentials in LBOE.
Use an approved password manager.
Client approval records are operator assertions, not e-signatures.
```

---

## 9. Sprint 28 Production Operations Dashboard

Add or improve a system/admin area.

Suggested route:

```text
/ui/system
```

or:

```text
/ui/admin/system
```

Show:

```text
database connectivity
Redis connectivity
current migration version
expected migration version
artifact root status
export root status
storage backend
auth mode
secure cookie config
environment profile
system_delivery_count
active preview link count
recent failed jobs
recent not-eligible jobs
recent errors if available
```

### 9.1 Health checks

Add or expose production-style health/readiness checks if not already present.

Possible routes:

```text
GET /health
GET /ready
GET /v1/system/status
```

If `/health` and `/ready` exist already, enhance their UI visibility rather than changing API semantics.

### 9.2 Configuration visibility

Operators/admins should see non-secret config status.

Show only safe booleans/labels, not secret values.

Example:

```text
Auth enabled: yes/no
Storage backend: local/s3
Export root configured: yes/no
Demo artifact root configured: yes/no
S3 bucket configured: yes/no
S3 credentials present: yes/no
```

Never render secrets.

---

## 10. Sprint 28 Admin Polish

Add or improve:

```text
operator list
operator role display
operator active/inactive status
current operator indicator
role permissions summary
audit event lookup or recent sensitive actions
```

Do not overbuild user management. This is internal v1.

---

## 11. Sprint 28 Accessibility and UX Baseline

Add basic UX/accessibility improvements:

```text
consistent button labels
forms with labels
error messages near forms
success messages after POST redirects
visible destructive action warnings
clear disabled/block states
semantic headings
reasonable contrast
keyboard-friendly navigation where practical
```

No need for a full design system, but define simple shared CSS classes:

```text
card
badge
warning
danger
success
muted
button-primary
button-secondary
layout-grid
section
```

---

## 12. Sprint 28 Tests

Add/update tests for:

```text
dashboard loads
navigation links present
system/admin page loads
lead detail shows safe next action
proposal safety banner visible
delivery credential warning visible
queues show empty states
role/admin pages load
system_delivery_count visible as 0
no sending buttons/routes introduced
config page does not expose secrets
```

---

## 13. Sprint 28 Documentation

Add/update:

```text
docs/OPERATOR_EXPERIENCE.md
docs/PRODUCTION_OPERATIONS.md
docs/OPERATOR_UI.md
docs/LIMITATIONS.md
README.md
```

Document:

```text
daily operator workflow
where to start
how to use queues
how to interpret block reasons
how to review system status
what the UI does not do
```

---

## 14. Sprint 28 Expected Commit

```text
feat(ui): improve operator experience and production operations
```

If split:

```text
feat(ui): improve operator navigation and work queues
feat(ops): add production operations dashboard
```

---

## 15. Sprint 28 Completion Report

Return:

```text
summary
commit SHA(s)
UI routes added/updated
system/admin routes added/updated
operator experience improvements
production operations improvements
tests run and results
smoke results
known limitations
architectural deviations
confirmation no sending/inbox sync/CRM sync/payment/contract/e-signature was added
confirmation Sprint 29 was not started
```


---

# Sprint 29 — Production Deployment + Real-world Operations

## 16. Sprint 29 Goal

Sprint 29 should answer this question:

```text
Can LBOE be deployed, backed up, restored, monitored, upgraded, and operated safely outside a developer laptop?
```

This is not necessarily a public SaaS launch. It is a controlled deployment-readiness sprint.

---

## 17. Sprint 29 Scope

Sprint 29 includes:

```text
deployment runbook
environment profiles
production-like docker compose or deployment manifests
backup and restore scripts/docs
migration runbook
secret handling guide
operator onboarding runbook
artifact storage configuration guide
preview link verification in deployed environment
monitoring/logging checklist
release upgrade process
rollback process
```

Sprint 29 does **not** include:

```text
public SaaS launch
automated sending
payments
billing
contracts
full multi-tenant architecture
managed cloud provisioning with real secrets
```

---

## 18. Deployment Profiles

Define and document environment profiles:

```text
local
pilot
production-like
test
```

Each profile should describe:

```text
database
Redis
artifact storage
export root
auth mode
secure cookies
allowed hostnames
logging level
debug mode
preview host/base URL
```

Update `.env.example` if needed with safe placeholders.

Do not commit secrets.

---

## 19. Deployment Runbook

Create:

```text
docs/DEPLOYMENT_RUNBOOK.md
```

It should cover:

```text
clone repo
set env
start services
apply migrations
create/admin operator
verify auth
verify storage
verify preview links
run smoke tests
create backup
restore backup
upgrade deployment
rollback deployment
```

Include exact commands where possible.

---

## 20. Production-like Compose / Deployment Artifacts

If appropriate, add:

```text
docker-compose.production-like.yml
```

or:

```text
deployment/
```

This should be safe and generic. No credentials.

A production-like config should:

```text
disable debug
enable auth
use persistent volumes
support external env file
configure health checks
avoid hardcoded secrets
```

If deployment-specific manifests are too speculative, provide docs and sample env files instead.

---

## 21. Backup and Restore

Add scripts or docs for PostgreSQL backup/restore.

Possible scripts:

```text
scripts/backup_postgres.py
scripts/restore_postgres.py
```

or shell/powershell documented commands.

Backup docs should include:

```text
database dump
artifact root backup
export root backup
restore sequence
verification after restore
```

Do not store backups in repo.

---

## 22. Monitoring and Logs

Document:

```text
structured logs
where logs go
what to monitor
failed jobs
migration state
system_delivery_count
preview access anomalies
storage errors
auth failures
```

If lightweight system status endpoint exists, reference it.

Potential docs:

```text
docs/MONITORING.md
docs/RUNBOOK_INCIDENTS.md
```

---

## 23. Upgrade and Rollback

Document upgrade process:

```text
pull latest
backup DB
backup artifacts
apply migrations
restart services
run smoke tests
verify UI
```

Rollback process:

```text
stop app
restore previous commit
restore DB backup if needed
restore artifact backup if needed
restart
run smoke tests
```

Be honest if database rollback is limited by migrations.

---

## 24. Operator Onboarding

Create:

```text
docs/OPERATOR_ONBOARDING.md
```

Include:

```text
first login
dashboard overview
daily queue workflow
campaign workflow
proposal workflow
delivery workflow
what not to do
security expectations
where credentials go
how to report issues
```

---

## 25. Sprint 29 Smoke / Verification Script

Add or update a deployment verification script if feasible:

```text
scripts/smoke_deployment_readiness.py
```

It should check:

```text
/health
/ready
/ui redirect/auth behavior
database migration current
storage configured
export root writable
system_delivery_count 0
proposal smoke optionally available
pilot smoke optionally available
```

Avoid environment-specific assumptions.

---

## 26. Sprint 29 Tests

Add tests for:

```text
deployment status redacts secrets
production-like settings parse
backup docs/scripts exist
operator onboarding docs exist
deployment smoke script exists
system status endpoint does not expose secrets
system_delivery_count remains 0
```

---

## 27. Sprint 29 Documentation

Add/update:

```text
docs/DEPLOYMENT_RUNBOOK.md
docs/OPERATOR_ONBOARDING.md
docs/MONITORING.md
docs/RUNBOOK_INCIDENTS.md
docs/BACKUP_RESTORE.md
docs/SECURITY_BOUNDARIES.md
README.md
.env.example
```

---

## 28. Sprint 29 Expected Commit

```text
chore(deploy): add production deployment and operations runbooks
```

If code is added:

```text
feat(ops): add deployment readiness verification
chore(docs): add deployment operations runbooks
```

---

## 29. Sprint 29 Completion Report

Return:

```text
summary
commit SHA(s)
deployment docs added
deployment scripts added
env/config changes
backup/restore process
monitoring/runbook docs
operator onboarding docs
tests run and results
smoke results
known limitations
architectural deviations
confirmation no sending/inbox sync/CRM sync/payment/contract/e-signature was added
confirmation Sprint 30 was not started
```


---

# Sprint 30 — Commercial Release Candidate v1

## 30. Sprint 30 Goal

Sprint 30 should answer this question:

```text
Can we confidently tag LBOE as v1 build-complete?
```

This is a release candidate sprint.

It should not add major features.

It should polish, document, test, and freeze.

---

## 31. Sprint 30 Scope

Sprint 30 includes:

```text
final UX polish
release checklist
acceptance testing
end-to-end test script
known limitations
v1 release notes
operator manual
admin manual
troubleshooting guide
commercial operating procedure
final safety review
v1 tag preparation
```

Sprint 30 does not include:

```text
new business workflows
automated sending
payments
billing
contracts
e-signature
major frontend rewrite
multi-tenant SaaS architecture
```

---

## 32. Final Acceptance Test

Create or update:

```text
scripts/smoke_v1_acceptance.py
```

This should exercise a representative path:

```text
health/readiness
auth/login
campaign creation
manual/synthetic business import
audit or audit-state simulation
score
brief
enrichment
demo
QA/review
preview link
outreach draft
readiness
manual CRM event
proposal generation/review/export
delivery project/checklist/milestone/export
reporting
system_delivery_count = 0
```

It may use synthetic data and fake adapters where appropriate.

The goal is to verify product coherence, not to depend on a live external scraper.

---

## 33. Final UX Polish

Polish:

```text
dashboard copy
empty states
error messages
success messages
button labels
danger warnings
help text
breadcrumbs
navigation consistency
safety banners
documentation links from UI if easy
```

No major redesign unless Sprint 28 left obvious defects.

---

## 34. Documentation Set

Create or update final docs:

```text
docs/V1_RELEASE_NOTES.md
docs/V1_ACCEPTANCE_CHECKLIST.md
docs/OPERATOR_MANUAL.md
docs/ADMIN_MANUAL.md
docs/TROUBLESHOOTING.md
docs/COMMERCIAL_OPERATING_PROCEDURE.md
docs/KNOWN_LIMITATIONS.md
docs/SAFETY_REVIEW.md
```

The documentation should explain:

```text
what LBOE does
who uses it
how to run it
how to operate it
how to deploy it
what it does not do
what safety boundaries exist
how to recover from failures
how to run acceptance tests
```

---

## 35. Commercial Operating Procedure

The commercial operating procedure should describe:

```text
choose vertical/geography
create campaign/pilot
discover/import leads
review evidence
generate demos
review demos
prepare outreach drafts
manually contact outside LBOE
record CRM outcomes
generate proposal
manage delivery
export records
retrospective
```

It should also state:

```text
No automated sending.
No copied reviews.
No unsupported claims.
No credential storage.
No contracts/e-signatures.
No payment collection.
```

---

## 36. Version / Release Marker

If the repo already uses versioning, update version appropriately.

If no versioning exists, add a simple release marker:

```text
docs/V1_RELEASE_NOTES.md
```

Potential tag instruction:

```text
v1.0.0-rc1
```

Do not create a Git tag unless explicitly requested by the product owner.

---

## 37. Final Safety Review

Create:

```text
docs/SAFETY_REVIEW.md
```

Confirm:

```text
system_delivery_count remains 0
no sending providers configured
no inbox sync
no CRM sync
no payment processing
no contracts/e-signature
preview tokens hashed
exports sanitized
credentials excluded
manual actions clearly labelled
operator assertions distinguished from verified facts
```

---

## 38. Sprint 30 Tests

Add/update tests for:

```text
v1 acceptance smoke exists
critical UI routes load
critical API routes work
proposal and delivery exports sanitize
system status redacts secrets
no sending route exists
system_delivery_count remains 0
docs exist
```

---

## 39. Sprint 30 Validation

Run:

```powershell
ruff format --check .
ruff check .
mypy apps packages integrations tests
pytest
python scripts/verify_bootstrap.py
docker compose config
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL --reset-synthetic
python scripts/smoke_pilot_flow.py --base-url http://127.0.0.1:8000
python scripts/smoke_pilot_operations.py --base-url http://127.0.0.1:8000
python scripts/smoke_proposals.py --base-url http://127.0.0.1:8000
python scripts/smoke_v1_acceptance.py --base-url http://127.0.0.1:8000
```

If auth/enrichment/delivery smoke scripts exist, run them too.

---

## 40. Sprint 30 Expected Commit

```text
chore(release): prepare v1 commercial release candidate
```

If split:

```text
test(release): add v1 acceptance smoke
docs(release): add v1 operator and admin manuals
chore(release): prepare v1 commercial release candidate
```

---

## 41. Sprint 30 Completion Report

Return:

```text
summary
commit SHA(s)
release docs added
acceptance scripts added
tests run and results
smoke results
known limitations
safety review summary
architectural deviations
v1 release candidate status
recommended tag, if any
confirmation no prohibited integrations were added
confirmation LBOE v1 is build-complete or list exact blockers
```

---

# Final Definition of Done for LBOE v1

LBOE v1 is build-complete when:

```text
1. Sprint 28, 29, and 30 are accepted.
2. Operator UI is coherent and usable.
3. Production operations are documented.
4. Deployment and backup/restore are documented.
5. Proposal workflow is smoke-tested.
6. Delivery workflow is covered by acceptance smoke or tests.
7. V1 acceptance smoke passes.
8. Documentation is sufficient for a new operator/admin.
9. Safety review is complete.
10. system_delivery_count remains 0.
11. No prohibited integrations were added.
12. Known limitations are documented.
```

At that point the project should move from build mode into:

```text
operate
sell
support
measure
iterate from real customer evidence
```
