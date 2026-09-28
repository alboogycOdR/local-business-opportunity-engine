# Deployment runbook

1. Copy `.env.example` to a local environment file and set secrets outside the repository.
2. Start PostgreSQL and Redis: `docker compose up -d postgres redis`.
3. Set `LBOE_DATABASE_URL`, run `python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL`, and verify `python scripts/smoke_deployment_readiness.py`.
4. Start the API with `PYTHONPATH=apps/api/src;packages/domain/src;packages/scoring/src;integrations/maps_scraper/src;integrations/website_auditor/src python -m uvicorn lboe_api.main:app --host 127.0.0.1 --port 8000`.
5. Run pilot/proposal/delivery smoke scripts. Back up PostgreSQL and the `artifacts/` and `exports/` roots before upgrades.

Production-like operation requires `LBOE_AUTH_ENABLED=true`, a non-default auth secret, secure cookies behind HTTPS, persistent PostgreSQL/Redis volumes, and an external secret manager. No credentials belong in LBOE tables or exports.
