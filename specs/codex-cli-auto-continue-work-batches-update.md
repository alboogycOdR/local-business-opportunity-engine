# Codex CLI Update Prompt — Continue Through Remaining Work Batches Automatically

Paste this prompt into Codex CLI from the repository root.

```markdown
# Update instruction — Continue through remaining work batches automatically

You previously received the remaining LBOE work-batch specs from the `specs/` folder.

Update your execution behavior as follows:

## New execution model

Do **not** stop after each work batch merely because the batch is complete.

Instead, after completing each work batch:

1. Run all required validation commands from that batch spec.
2. Fix any validation failures.
3. Commit the completed batch using the expected commit message(s).
4. Push the commit(s) to `origin main`.
5. Verify the push succeeded.
6. Confirm the working tree is clean except for intentionally untracked local-only files such as `specs/`.
7. Proceed automatically to the next work batch in sequence.

## Work-batch order

Continue in this order:

```text
Work Batch 2: Sprint 20–21 — Calibration + Enrichment
Work Batch 3: Sprint 22–23 — Demo Quality + Outreach Workflow
Work Batch 4: Sprint 24–25 — Deployment + Artifact Hosting Hardening
```

Sprint 19 is already complete and accepted, so do not redo it.

Current accepted baseline:

```text
c8a2572eab8a257b5be53add071911fa966f3635
chore(pilot): execute second controlled real pilot batch
```

## Push behavior

After each successful batch commit:

```powershell
git status
git log --oneline -5
git push origin main
git status
```

The expected result after push is:

```text
Your branch is up to date with 'origin/main'
nothing to commit, working tree clean
```

It is acceptable if `specs/` remains untracked, because those files are local handoff specs and should not be committed unless explicitly instructed.

## Stop conditions

Stop immediately and report back if any of the following happens:

```text
validation fails and cannot be fixed cleanly
pytest fails
mypy fails
ruff fails
migration verification fails
smoke flow fails
git push is rejected
merge/rebase conflict occurs
a safety boundary would be violated
a spec requires product-owner approval
a proposed change would add automated sending, inbox sync, CRM sync, payments, or external messaging integration
```

## Safety boundary

Across all remaining batches, do not add:

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
autonomous outreach
autonomous follow-ups
raw preview token exports
raw scraper payload resale
```

Manual outreach must remain outside LBOE.

`system_delivery_count` must remain `0`.

## Reporting after each batch

After each batch is committed and pushed, produce a short checkpoint summary containing:

```text
Completed work batch:
Sprint(s):
Commit SHA(s):
Validation results:
Smoke results:
Push status:
Safety confirmation:
Next batch started:
```

Then continue to the next batch automatically.

## Final stop

After Work Batch 4 / Sprint 24–25 is committed and pushed, stop.

Do **not** start Sprint 26.

Final report must include:

```text
all commit SHAs
validation results by batch
smoke results by batch
migrations added
major files added/updated
known limitations
architectural deviations
confirmation system_delivery_count remained 0
confirmation no automated sending/inbox sync/CRM sync/external messaging/payment integration was added
confirmation Sprint 26 was not started
```

Begin now from the current `main` branch, with Sprint 20–21.
```
