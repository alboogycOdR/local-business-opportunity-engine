# Deployment runbook

1. Copy `.env.example` to a local environment file and set secrets outside the repository.
2. Start PostgreSQL and Redis: `docker compose up -d postgres redis`.
3. Set `LBOE_DATABASE_URL`, run `python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL`, and verify `python scripts/smoke_deployment_readiness.py`.
4. Start the API with `PYTHONPATH=apps/api/src;packages/domain/src;packages/scoring/src;integrations/maps_scraper/src;integrations/website_auditor/src python -m uvicorn lboe_api.main:app --host 127.0.0.1 --port 8000`.
5. Run pilot/proposal/delivery smoke scripts. Back up PostgreSQL and the `artifacts/` and `exports/` roots before upgrades.

Production-like operation requires `LBOE_AUTH_ENABLED=true`, a non-default auth secret, secure cookies behind HTTPS, persistent PostgreSQL/Redis volumes, and an external secret manager. No credentials belong in LBOE tables or exports. The current private VPS deployment is intentionally bound to the Tailscale network and keeps the token gate disabled; do not expose that profile publicly without enabling authentication and HTTPS.

## Ubuntu Docker deployment

The production profile is `docker-compose.prod.yml`. It runs PostgreSQL, Redis, and the API, applies forward-only migrations on API startup, persists `artifacts/` and `exports/`, and binds the API to `127.0.0.1:8095` for a host reverse proxy.

```bash
cp .env.example .env
# Set a long random POSTGRES_PASSWORD, LBOE_AUTH_SECRET,
# LBOE_OPERATOR_AUTH_TOKEN, and LBOE_AUTH_ENABLED=true in .env.
docker compose -f docker-compose.prod.yml up -d --build
curl http://127.0.0.1:8095/health
curl http://127.0.0.1:8095/ready
```

Keep discovery disabled unless the local scraper is deliberately deployed and configured. Put Caddy or another HTTPS reverse proxy in front of `127.0.0.1:8095`; do not expose PostgreSQL or Redis publicly. Back up the named database/Redis volumes and the artifact/export directories before upgrades.

For the current Tailscale VPS setup, LBOE runs with the host-only
`docker-compose.vps.yml` override. The Maps scraper remains a separate service
on the private Docker network and is not vendored into LBOE. Verify `/health`,
`/ready`, `/v1/system/status`, and `/ui/opportunities` after upgrades. Keep the
scraper's public host port closed; LBOE reaches it over the internal service
network.
