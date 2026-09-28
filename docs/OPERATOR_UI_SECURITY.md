# Operator UI security

The internal UI has an optional signed session gate backed by PostgreSQL session
records, secure-cookie configuration, logout/revocation, and an operator token
bootstrap. Role fields remain explicit on operators; sensitive workflow actions
continue to pass backend lifecycle and suppression checks. This is not a public
SaaS authentication system and should be placed behind private network access.
