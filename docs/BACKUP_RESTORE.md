# Backup and restore

Create a database dump with `pg_dump "$env:LBOE_DATABASE_URL" > lboe.sql`. Back up `artifacts/` and `exports/` separately. Restore PostgreSQL first, restore artifact/export roots, apply migrations, then run `/ready`, `scripts/smoke_deployment_readiness.py`, and the synthetic smoke flows. Database migrations are forward-only; restore a compatible database backup rather than editing migration history.
