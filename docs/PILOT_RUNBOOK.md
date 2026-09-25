# Pilot Runbook — First 20–50 Businesses

## Objective

Test whether the system can reliably identify actionable digital gaps, generate trustworthy demos, and produce enough operator/business interest to justify further automation.

## Before the pilot

- Choose one vertical.
- Choose one geography.
- Confirm the campaign's source and outreach policy.
- Configure one demo template.
- Set score threshold to 70 initially.
- Disable automatic sending.
- Set a hard daily demo-generation cap.

## Step 1 — Discover/import

Target 50–100 raw candidates so that 20–50 can survive qualification.

Record:

- source
- source identifier/URL
- observed date
- name/category/locality
- any source storage limitations

## Step 2 — Deduplicate

Review ambiguous matches manually.

Do not merge automatically when:

- similar names have different addresses
- chains have multiple branches
- a business has moved
- category and contact details conflict

## Step 3 — Cheap qualification

Reject/hold:

- clearly closed businesses
- irrelevant category
- duplicates
- no reliable identity
- policy conflicts

Do not reject merely because a website exists.

## Step 4 — Audit

For every qualified business:

- resolve website
- capture desktop/mobile screenshot
- measure website health
- identify booking/WhatsApp/call/form paths
- store structured findings

## Step 5 — Score

Calculate `opportunity-v1` and review:

- total
- components
- holds
- data confidence

Manually inspect the top 10 to validate whether scoring feels sensible before generating all demos.

## Step 6 — Enrich selected leads

For high-score leads, retrieve only the facts needed to build a truthful demo. Prefer business-owned sources.

## Step 7 — Generate demos

Generate 10–20 demos first, not all leads.

Pass automated QA, then human review.

Record review outcome:

- approved first pass
- approved after regeneration
- rejected due to weak evidence
- rejected due to design
- rejected due to incorrect facts

## Step 8 — Create offers

Map the top detected gaps to capability packages.

Do not invent pricing based on the score. Use campaign pricing configuration.

## Step 9 — Outreach

Apply jurisdiction/channel policy, consent status and suppression checks. Human approves every message in the pilot.

## Step 10 — Record outcomes

At minimum:

- sent/contacted
- reply
- interested/not interested
- meeting
- proposal
- won/lost
- reason lost

## Pilot review questions

1. Did high-score leads look meaningfully better than medium-score leads?
2. Which individual score components correlated with replies/meetings?
3. Which demos required regeneration and why?
4. Which vertical template sections were most persuasive/useful?
5. Which data sources caused factual or policy problems?
6. What was the operator time per approved demo?
7. What was the processing cost per approved demo?
8. Which offer package was easiest to explain?

## Exit criteria

Only scale discovery/generation after the pilot demonstrates:

- acceptable factual accuracy
- manageable compliance process
- reasonable cost per approved demo
- a repeatable operator workflow
- some measurable commercial signal
