# Sprint 3 — Digital Presence Auditor

Sprint 3 adds a provider-neutral website resolver and deterministic digital
presence audit. The Playwright adapter visits only the resolved homepage,
uses bounded desktop/mobile contexts, and stores screenshots as filesystem
artifacts referenced by `audit_artifacts`, never as PostgreSQL blobs.

Implemented finding families include availability, HTTPS/resolution,
viewport/overflow, booking, WhatsApp, click-to-call, contact/conversion
links, title/meta/canonical, structured data, Open Graph, H1, image alt,
document language, console errors, and failed first-party requests.

All URLs are DNS-resolved before navigation and every redirect destination is
revalidated. Loopback, private, link-local, reserved, metadata, file, ftp,
and unsupported schemes are blocked. This is an audit baseline, not a WCAG
certification or subjective SEO/design score.

The MVP permits an explicit `DISCOVERED -> AUDITING -> AUDITED` path for a
lightweight homepage audit because Sprint 2 discovery does not yet include a
separate enrichment worker. The transition is recorded in `pipeline_events`.

Local setup requires `playwright install chromium`. API endpoints:

* `POST /v1/businesses/{business_id}/audit`
* `GET /v1/businesses/{business_id}/audits`
* `GET /v1/audits/{audit_id}`

The accepted real discovery smoke test used `gosom/google-maps-scraper:latest`
at digest `sha256:e205c02913c5a69c16fc2094b8e5b194a2f655166d2c1126d50548d216e6b1b2`
on 2026-09-25: 20 upstream places, 5 candidates, 5 imported, 29 source
observations, 5 external identities, and zero ambiguous records.

Real audit smoke test: `The Fox & Vixen` (`https://thefoxandvixen.co.za/`)
was attempted once with one homepage and desktop/mobile contexts. The site
returned a TLS connection failure from the local environment, so the audit
persisted the deterministic `WEBSITE_UNREACHABLE` finding and no screenshots;
no forms, bookings, messages, or transactional actions were performed.
