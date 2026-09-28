# Sprint 16 real pilot notes

## Lead intake

| Business name | Source | Website | Contact present? | Imported? | Duplicate/ambiguous? | Notes |
|---|---|---|---|---|---|---|
| Lila Vie Hair | maps scraper | Facebook page | phone, public URL | yes | no | Source ID present |
| Excentric on Kloof | maps scraper | excentric-hair.co.za | phone, website | yes | no | Existing healthy-site pattern |
| Spoilt Hair Salon | maps scraper | spoilthairsalon.co.za | phone, website | yes | no | Website audited |
| Mop Hair | maps scraper | mophair.co.za | phone, website | yes | no | Website audited |
| Palladium Hair Company | maps scraper | palladiumhair.com | phone, website | yes | no | Website audited |
| Crown Of Beauty Hair Design | maps scraper | none returned | phone | yes | no | Starter-website candidate |
| Elegant Head Lover's Salon | maps scraper | none returned | phone | yes | no | Demo QA failed; not shared |
| The Fox & Vixen | maps scraper | thefoxandvixen.co.za | phone, website | yes | no | Website audited |
| Blue Lemon Hair & Beauty | maps scraper | bluelemonhair.com | phone, website | yes | no | Website audited |
| Natural Image hair and Beauty salon | maps scraper | naturalimage.co.za | phone, website | yes | no | Website audited |

## Audit outcomes

| Result | Count |
|---|---:|
| Audit runs | 10 |
| Healthy website findings | 5 |
| HTTP error findings | 2 |
| TLS failure findings | 1 |
| Missing website findings | 0 |

Common findings included booking, click-to-call, contact form, service
catalogue, map/location and WhatsApp signals. Browser console errors occurred
on 2 records and failed first-party requests on 1.

## Score / brief / demo outcomes

| Metric | Result |
|---|---:|
| Scores | 10 |
| Average score | 67.6 |
| High / medium / low | 5 / 2 / 3 |
| Briefs | 10 |
| Demos generated | 2 |
| QA passed / failed | 1 / 1 |
| Approved demos | 1 |

## Preview / outreach readiness

| Metric | Result |
|---|---:|
| Preview links | 1 |
| Draft packages ready | 1 |
| Readiness reviews | 2 |
| Leads at OUTREACH_READY | 1 |
| Manual contacts | 0 |

## CRM outcomes

No replies, meetings, proposals, wins, or losses were recorded. No manual
contact was performed.

## Operator observations

| Issue | Impact | Suggested fix | Sprint candidate |
|---|---|---|---|
| Readiness requires an active operator | Initial activation blocked safely | Add clearer operator setup hint | Sprint 17 |
| Audit evidence crossed score/brief persistence as non-JSON values | Three scores initially failed and brief persistence rejected list evidence | Added JSON projection and evidence normalization; retried affected scores | Completed Sprint 16 |
| One no-website demo failed QA | Demo was not shared | Keep QA gate; inspect template evidence | Sprint 17 |
| Some results lacked website or source ID | Lower confidence and no immediate demo | Retain provenance and manual review | Sprint 17 |
