# Sprint 19 — Batch 2 real pilot notes

This was a controlled, dry-run Cape Town hair-salon batch using the local
upstream maps scraper. Contact values are intentionally omitted.

## Lead intake

| Metric | Result |
|---|---:|
| Requested | 25 |
| Returned by scraper | 22 |
| Imported businesses | 21 |
| Duplicates | 1 |
| Ambiguous candidates | 0 |
| Source observations | 128 |
| External identities | 12 |

The scraper returned fewer than the target cap; volume was not increased.

## Audit outcomes

| Outcome | Count |
|---|---:|
| Completed audit runs | 21 successful records, plus retry history |
| Healthy website finding | 18 |
| HTTP error finding | 3 |
| TLS failure finding | 1 |
| Browser console error observations | 6 |
| Failed first-party request observations | 2 |

Five initial audit jobs failed due to an operator sequencing mistake and were
retried once after restoring the documented audit transition path. No broad
crawl was performed.

## Score, brief, and demo outcomes

| Metric | Result |
|---|---:|
| Scores / briefs | 21 / 21 |
| Average score | 61.86 |
| Score bands | 8 high / 2 medium / 11 low |
| `generate_demo` actions | 4 |
| Demos generated | 4 |
| QA passed / failed | 3 / 1 |
| Approved demos | 3 |

The QA-failed demo remained blocked from sharing. Healthy-site records were
generally classified for conversion or technical cleanup rather than a full
starter rebuild; Excentric on Kloof remained `score_only`.

## Preview and readiness

Three approved demos received controlled seven-day preview links. Three draft
packages and three `prepare_consent_review` records were created. No lead was
advanced to `OUTREACH_READY`, `CONTACTED`, or any later CRM state.

## Manual outreach / CRM outcomes

None. Manual outreach remains outside LBOE. There are no message transcripts,
reply assertions, meetings, proposals, wins, or losses for this batch.

## Operator observations

- Readiness was clear once an active operator and source-policy acknowledgement
  were present.
- The main friction was the per-lead lifecycle/audit sequencing and the lower
  than requested scraper return count.
- Existing score, brief, QA, preview, and export explanations were sufficient
  to keep the dry run reviewable.
- No batch expansion to 50 was attempted.
