# Sprint 16 pilot outcome report

## Pilot

- Name: Cape Town Hair Salons Pilot - Sprint 16
- Vertical: hair_salon
- Geography: Cape Town, South Africa
- Window: 2026-09-28, Africa/Johannesburg
- Operators: sprint16-operator / local pilot operator
- Batch size: 10 real businesses
- Mode: dry-run configuration; readiness and preview workflow exercised
- Source policy: `pilot-source-v1` acknowledged
- System delivery count: **0**

## Funnel and quality results

| Metric | Count |
|---|---:|
| Discovered/imported | 10 |
| Duplicates | 0 |
| Ambiguous | 0 |
| Audited | 10 |
| Healthy website findings | 5 |
| HTTP/TLS issue findings | 3 combined |
| Scored | 10 |
| Briefs | 10 |
| Demos generated | 2 |
| Demo QA passed / failed | 1 / 1 |
| Approved demos | 1 |
| Preview links | 1 |
| Outreach drafts ready | 1 |
| Readiness approvals | 1 selected lead |
| Manual contacts | 0 |
| Replies / meetings / proposals / wins / losses | 0 / 0 / 0 / 0 / 0 |

Score bands were high 5, medium 2, and low 3, with an average score of 67.6.
There were 58 source observations and 5 external identities in the campaign.

## Qualitative findings

Best-fit patterns were businesses with a clear public website or no verified
website, a reachable public contact channel, and enough factual evidence for a
truthful concept. Common audit signals were booking, WhatsApp, click-to-call,
contact form, service catalogue, map/location, and responsive/SEO findings.

Weak-fit patterns included listings with no website, incomplete source IDs, or
sites with technical failures where a demo could not be safely justified. One
demo failed QA and was not shared.

Operator friction was primarily setup clarity: an active operator is required
before readiness can pass. Real persistence defects were found when score
components attempted to store `AuditEvidence` model objects and the brief
layer expected dictionary evidence. JSON projection and evidence normalization
were corrected; all affected scores and briefs were retried successfully.

No business objections or reply quality data exists because no contact was
performed. False-positive/false-negative calibration is therefore deferred.

## Export pack

The controlled pilot export run generated:

- `pilot-summary.json`
- `pilot-report.json`
- `leads.csv`
- `demo-links.csv`
- `operator-activity.csv`

The export contains no raw preview tokens, secrets, credentials, or raw
scraper payload dumps.

## Final decision and Sprint 17 recommendation

The system safely completed a small real discovery-to-readiness rehearsal and
is suitable for a cautiously expanded operator pilot. Sprint 17 should focus
on batch operator ergonomics, audit/score observability, and calibration from
real human outcomes—not automated sending. Manual outreach should remain
outside LBOE until the operator explicitly chooses to run it under the source
policy and applicable consent rules.

No automated sending was performed. No inbox sync or CRM sync was added.
`system_delivery_count` remained zero.
