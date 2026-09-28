# Sprint 21 — source-aware enrichment

Sprint 21 adds provider-neutral contracts and a minimal homepage adapter. It
fetches only an already-known HTTP(S) homepage, extracts contact/action links
and service signals, and stores normalized facts with source type, URL,
confidence, observation time, evidence, and policy.

Endpoints:

- `POST /v1/businesses/{id}/enrich`
- `GET /v1/businesses/{id}/enrichments`
- `GET /v1/enrichments/{id}`

The adapter does not broad-crawl, copy reviews, infer sensitive traits, send
messages, or integrate inboxes/CRMs. Enrichment history is append-only.
