# scripts

- `migrate.py` applies ordered PostgreSQL migrations and records
  `schema_migrations`.
- `seed_pilot.py` creates or resets only the synthetic Sprint 13 pilot data.
- `smoke_pilot_flow.py` drives the local API happy path without provider calls
  or message delivery.
- `verify_bootstrap.py` checks required repository bootstrap files.
