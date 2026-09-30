# Operator UI security

The internal UI has a username/password login backed by salted scrypt password
hashes and PostgreSQL session records. Sessions support logout/revocation and
expire after eight hours, or after 30 days when the operator explicitly selects
"remember me". When `LBOE_AUTH_ENABLED=true`, versioned API routes require the
separate operator token as an HTTP Bearer credential. `/health` and `/ready` remain
available to infrastructure probes. Set `LBOE_CSRF_ENABLED=true` to validate
same-origin writes to the cookie-authenticated UI. Role fields remain explicit
on operators; sensitive workflow actions continue to pass backend lifecycle
and suppression checks. This is not a public SaaS authentication system and
should be placed behind private network access.

When `LBOE_ENV=production`, startup fails unless `LBOE_AUTH_ENABLED`,
`LBOE_CSRF_ENABLED`, and `LBOE_SECURE_COOKIES` are true, the operator API token
is at least 32 characters, and `LBOE_AUTH_SECRET` is a non-default value of at
least 32 characters. A valid `LBOE_OPERATOR_USERNAME` and generated
`LBOE_OPERATOR_PASSWORD_HASH` are also required. Terminate TLS before the
application so secure cookies can be used.
