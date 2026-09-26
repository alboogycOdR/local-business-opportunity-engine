# LBOE Pilot Runbook

This runbook is for a local, synthetic or operator-controlled 10–50 lead
pilot. No command in this runbook sends an external message.

## Prerequisites

- Windows PowerShell 7 or a Unix shell
- Docker Desktop
- Python 3.12 and the project virtual environment
- PostgreSQL and Redis available through Docker Compose

Copy `.env.example` to `.env` and keep secrets out of the repository.

## Start and migrate

```powershell
docker compose up -d postgres redis
$env:LBOE_DATABASE_URL = "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

The migration runner applies the numbered files once and records them in
`schema_migrations`. It is safe to rerun.

## Validate and seed

```powershell
pytest
python scripts/verify_bootstrap.py
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL
```

The seed creates only synthetic records marked with policy seed key
`sprint13-pilot`. To reset only those records:

```powershell
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL --reset-synthetic
```

## Run API and smoke flow

In a second PowerShell window:

```powershell
$env:LBOE_DATABASE_URL = "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
uvicorn lboe_api.main:app --reload
```

Then:

```powershell
python scripts/smoke_pilot_flow.py --base-url http://127.0.0.1:8000
Invoke-RestMethod http://127.0.0.1:8000/v1/reports/pilot
```

The smoke output includes campaign, business, demo, draft, manual-log and CRM
event IDs. It records a synthetic manual execution only; the response must
show `delivery_performed_by_system: false` and report `system_delivery_count`
as zero.

## Inspect artifacts and states

Audit artifacts are under `artifacts/audits`; concept demos are under
`artifacts/demos/{demo_id}`. These paths are local and ignored by Git. A normal
happy path ends in `MEETING` after operator-entered reply and meeting events.
`CONTACTED` means an operator logged contact, not that LBOE sent anything.

## Troubleshooting

- `connection refused`: run `docker compose ps` and wait for the Postgres
  health check.
- `relation does not exist`: rerun `python scripts/migrate.py` against the
  same database URL.
- API readiness is `503`: verify Redis is running; `/health` is process-only.
- stale synthetic rows: use `--reset-synthetic`, never broad database deletion.
- missing demo artifacts: check `LBOE_DEMO_ARTIFACT_ROOT` and filesystem
  permissions.
- maps/audit provider errors: keep provider flags disabled for the synthetic
  pilot; the seed and smoke scripts require no external services.

## Operator pilot checklist

For a real 10–50 lead pilot, choose one vertical and geography, confirm the
campaign source/outreach policy, configure one template, keep automatic sending
disabled, and set a daily demo cap. Record source, identifier, observed date,
identity fields, and storage limitations for each candidate. Review ambiguous
matches manually; do not merge conflicting names, addresses, branches, or
categories automatically.

Audit qualified businesses before scoring. Review score components and holds on
the top leads before generating demos. Generate a small batch first, pass QA,
and record human review outcomes. Offers must use configured campaign pricing,
not score-derived prices. Every message remains human-approved and every
outcome should be recorded as an explicit CRM event.

Pilot review questions include: which score components correlate with replies or
meetings, which demos need regeneration, which sources cause factual/policy
issues, operator time per approved demo, processing cost, and which offer is
easiest to explain. Scale only after factual accuracy, compliance handling,
cost, and operator workflow are repeatable.
