# scripts

- `migrate.py` applies ordered PostgreSQL migrations and records
  `schema_migrations`.
- `seed_pilot.py` creates or resets only the synthetic Sprint 13 pilot data.
- `smoke_pilot_flow.py` drives the local API happy path without provider calls
  or message delivery.
- `verify_bootstrap.py` checks required repository bootstrap files.
- `smoke_proposals.py` verifies synthetic proposal generation, review, export, and safety scanning.

Delivery projects are operator-managed and never store credentials. Use an approved password manager for access details; local delivery exports are not sent by LBOE.
