# Deployment readiness

Sprint 24 supports controlled internal deployment. Set `LBOE_AUTH_ENABLED=true`,
provide a non-default `LBOE_AUTH_SECRET` and `LBOE_OPERATOR_AUTH_TOKEN`, and
enable secure cookies behind HTTPS. The login is an internal token gate, not a
public identity provider or SaaS tenancy system. Keep API and operator access
on a private network.

Readiness must verify PostgreSQL, Redis, current migrations, artifact roots,
and that system delivery remains disabled.
