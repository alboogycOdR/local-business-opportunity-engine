# Real pilot operator checklist

Check each item and record evidence in `SPRINT_15_EVIDENCE_LOG.md`.

## Pre-flight

- [ ] Postgres and Redis healthy; migrations applied
- [ ] Pilot profile and target/caps reviewed
- [ ] `system_delivery_count` is zero

## Source policy

- [ ] Source policy version matches the pilot
- [ ] Operator acknowledgement saved
- [ ] No raw scraped payload resale or copied reviews

## Dry-run

- [ ] Pilot remains dry-run during rehearsal
- [ ] No manual contact or CRM outcome records created from rehearsal

## Lead intake / audit / score

- [ ] Import/discovery source and observation time recorded
- [ ] Ambiguous candidates retained for review
- [ ] Website audit and score evidence reviewed

## Demo and review

- [ ] Only eligible leads receive deterministic demos
- [ ] QA passed and human checklist approved
- [ ] Preview links are expiring and tokens are never exported

## Outreach and CRM

- [ ] Draft and readiness checks passed
- [ ] Manual contact, if any, happened outside LBOE
- [ ] Contact/reply/meeting records are explicit operator assertions

## Export / retrospective / shutdown

- [ ] Five export files generated and sanitized
- [ ] Retrospective saved without changing funnel state
- [ ] Pilot paused or closed when the run ends

At every section: LBOE does not send messages. Manual outreach happens outside
LBOE. Logging contact records only records operator assertions. Concept previews
are not official business websites.
