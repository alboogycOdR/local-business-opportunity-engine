# Database

Sprint 1 must establish a real migration toolchain and create the foundational schema from an empty PostgreSQL database.

Required initial entities are documented in `docs/SPRINT_01.md`.
# Database

Sprint 1 uses PostgreSQL as the system of record. Start the local service with
`docker compose up -d postgres`, then apply `migrations/0001_initial.sql`:

```bash
psql "$DATABASE_URL" -f infrastructure/database/migrations/0001_initial.sql
```

The schema uses UUID primary keys, provenance/source observations, auditable
pipeline events, suppression entries, and unique campaign-scoped identity keys.
The API's startup `create_all` fallback is intended only for local/test bootstrap;
production changes must be applied as migrations.
