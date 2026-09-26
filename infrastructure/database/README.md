# Database

Sprint 1 must establish a real migration toolchain and create the foundational schema from an empty PostgreSQL database.

Required initial entities are documented in `docs/SPRINT_01.md`.
# Database

PostgreSQL is the system of record. Start the local service with
`docker compose up -d postgres`, then apply all ordered migrations with:

```bash
python scripts/migrate.py --database-url "$LBOE_DATABASE_URL"
```

The runner creates an append-only `schema_migrations` table, applies files in
numeric order, and safely skips versions already recorded. It is safe to run
again after a partial or completed setup. On Windows PowerShell:

```powershell
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

The schema uses UUID primary keys, provenance/source observations, auditable
pipeline events, suppression entries, and unique campaign-scoped identity keys.
The API's startup `create_all` fallback is disabled by default and intended only
for local/test bootstrap; production changes must be applied through this runner.
