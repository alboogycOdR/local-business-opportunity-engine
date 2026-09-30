# Focused security review — 2026-09-30

## Scope

This review covered the internal API and operator UI authentication boundary,
cookie sessions and CSRF, public concept preview tokens, artifact path handling,
website audit and enrichment network access, Redis job delivery, secret scanning,
and the no-send outreach boundary. It was a source review with regression tests,
not an independent penetration test.

## Trust boundaries and protected assets

- Operators enter through the private UI or versioned API.
- PostgreSQL contains business, provenance, consent, suppression, and workflow
  records and remains authoritative for job state.
- Redis transports job identifiers only; it is not a prospect-data store.
- Audit and enrichment workers make outbound requests to untrusted business
  websites.
- Artifact roots contain screenshots, generated concepts, and exports.
- External preview URLs cross the private-network boundary and therefore use
  opaque, hashed, expiring, revocable tokens.

## Findings and controls

| Area | Finding | Control/status |
|---|---|---|
| API access | Versioned routes were reachable without authentication. | Bearer authentication gates `/v1/*` when auth is enabled. Production now requires auth at startup. |
| UI writes | Cookie-authenticated writes could run without CSRF enforcement. | Same-origin and stored CSRF-cookie validation is available and mandatory in production. |
| Deployment configuration | Production could start with local defaults, weak secrets, or insecure cookies. | Startup now fails closed unless auth, CSRF, secure cookies, and unique 32-character secrets are configured. |
| Enrichment SSRF | Homepage enrichment followed redirects automatically without the audit resolver's public-address checks. | Initial URLs and every redirect are now validated, automatic redirects are disabled, loops are rejected, and accepted HTML is capped at 2 MB. |
| Audit SSRF | Untrusted audit URLs can target internal services. | The resolver rejects non-HTTP schemes, private/special IPs, metadata hosts, and unsafe redirect targets. |
| Preview access | Share links could leak or remain useful after suppression. | Raw tokens are never stored, links expire and can be revoked, suppression blocks access, and responses use no-store, no-referrer, noindex, CSP, and frame restrictions. |
| Artifact traversal | Database paths could address files outside configured roots. | Serving resolves canonical paths and requires the configured artifact root to be a parent. |
| Queue durability | A committed job could be stranded when its initial Redis publish failed. | The worker republishes aged queued rows with short-lived Redis deduplication; PostgreSQL status claims prevent duplicate execution. |
| Sensitive errors | Provider failures could persist secrets or payloads. | Worker failures store only the exception class; Redis messages contain only job IDs. |
| Outreach | Workflow changes could accidentally become delivery actions. | No provider integration exists; contact and CRM records remain operator assertions and suppression/consent gates remain authoritative. |

## Residual risks and deployment requirements

- The internal auth model uses one operator bootstrap token and does not provide
  per-user authorization. Keep the service behind private network access until
  identity and role enforcement are implemented.
- Add infrastructure rate limiting for login and API authentication failures.
- Enforce worker egress policy at the network layer. Application DNS checks
  reduce SSRF risk but do not replace egress filtering against DNS rebinding or
  transport-level routing attacks.
- Continue the planned migration from hand-built HTML toward templates with
  automatic escaping, and add a restrictive CSP to all authenticated UI pages.
- Run an independent penetration test and organization-specific threat-model
  review before public exposure.

No automatic sending, inbox synchronization, CRM provider integration, payment
processing, or credential storage was introduced by this remediation.
