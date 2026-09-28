# Sprint 19 — Batch 2 outcome report

## Executive result

Batch 2 completed as a controlled dry run on 2026-09-28. The local scraper
returned 22 candidates against the 25-lead target. Twenty-one businesses were
imported and one was conservatively deduplicated. No ambiguous records were
created and no external message was sent.

## Metrics

| Metric | Batch 2 |
|---|---:|
| Candidates returned / imported | 22 / 21 |
| Duplicates / ambiguous | 1 / 0 |
| Source observations / external identities | 128 / 12 |
| Scores / briefs | 21 / 21 |
| Average score | 61.86 |
| Score bands | 8 high / 2 medium / 11 low |
| Healthy / HTTP-error / TLS-error findings | 18 / 3 / 1 |
| Demos generated | 4 |
| QA passed / failed | 3 / 1 |
| Approved demos | 3 |
| Controlled preview links | 3 |
| Outreach drafts / readiness reviews | 3 / 3 |
| `OUTREACH_READY` / manual contacts | 0 / 0 |
| Replies / meetings / proposals / wins / losses | 0 / 0 / 0 / 0 / 0 |
| System delivery count | **0** |

The report endpoint recorded 26 audit rows because the five failed initial jobs
and their successful retry records are preserved in append-only history. The
21 businesses each have a successful audit outcome.

## Comparison with Sprint 16

| Dimension | Sprint 16 | Batch 2 |
|---|---:|---:|
| Requested / returned / imported | 10 / 10 / 10 | 25 / 22 / 21 |
| Duplicate rate | 0% | 4.5% of returned candidates |
| Ambiguous rate | 0% | 0% |
| Score bands | 5 high / 2 medium / 3 low | 8 high / 2 medium / 11 low |
| Average score | 67.6 | 61.86 |
| Demos generated | 2 | 4 |
| QA pass / fail | 1 / 1 | 3 / 1 |
| Approved demos | 1 | 3 |
| Preview links | 1 | 3 |
| Manual contacts / replies / meetings | 0 / 0 / 0 | 0 / 0 / 0 |

Batch 2 increased volume and approved-demo throughput without crossing the
manual-contact boundary. The lower average score is consistent with a broader
returned set and should not be interpreted as business quality.

## Quality findings and recommendations

Common evidence included booking, WhatsApp, click-to-call, contact forms,
service catalogue, map/location, responsive, SEO, and browser-network signals.
The primary false-positive risk remains a high score driven by sparse/no-site
facts; the demo gate correctly limited starter demos to four eligible records.

Recommended Sprint 20–21 work:

1. calibrate no-website and healthy-site score components using the two pilot
   distributions;
2. add source-aware enrichment for known website URLs and action links;
3. preserve explicit weak-evidence labels and QA explanations;
4. collect real operator outcomes before changing weights further.

## Export verification

The export pack contains:

- `pilot-summary.json`
- `pilot-report.json`
- `leads.csv`
- `demo-links.csv`
- `operator-activity.csv`

Files were checked for preview-token URL patterns, credentials, secrets,
authorization values, and raw scraper payload fields. None were present.

## Decision

Do not expand to 50 yet. Batch 2 is suitable for a reviewed second batch, but
the next step should be calibration and evidence enrichment, not automated or
bulk outreach.
