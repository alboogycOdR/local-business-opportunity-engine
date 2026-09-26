# Controlled Demo Preview Hosting

Preview sharing is limited to generated concept demos. It is not production
website hosting and does not imply affiliation with the business.

Only QA-passed or approved demos with a recorded artifact may be shared.
Suppressed businesses and rejected/failed demos are blocked. A generated
`secrets.token_urlsafe` token is shown once to the operator; PostgreSQL stores
only its SHA-256 hash. Links expire within the operator-selected 1–30 day
window and can be revoked.

`GET /preview/{token}` validates the hash, status, expiry, demo artifact root,
and disclaimer before serving HTML. Access events store outcome and minimal
metadata, not raw IP addresses or user agents. Artifact paths are constrained
to the configured demo artifact root; directory listing and traversal are not
available.
