# Sprint 15 controlled real pilot launch runbook

This pack prepares a 10–50 lead Cape Town hair-salon pilot. Start in `dry_run`;
only activate after readiness passes. LBOE never sends messages: manual contact
happens outside LBOE and logging records operator assertions only.

## 1. Checkout and services

```powershell
git checkout 08f3ab1468a1c08b8f06604f30b8abf003d32565
docker compose up -d postgres redis
$env:LBOE_DATABASE_URL = "postgresql+psycopg://lboe:lboe_dev_only@localhost:5432/lboe"
python scripts/migrate.py --database-url $env:LBOE_DATABASE_URL
```

## 2. Rehearse safely

```powershell
python scripts/seed_pilot.py --database-url $env:LBOE_DATABASE_URL --reset-synthetic
python scripts/smoke_pilot_flow.py --base-url http://127.0.0.1:8000
python scripts/smoke_pilot_operations.py --base-url http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000/ui`, then `/ui/pilots`. Create the pilot using
`config/pilots/cape-town-hair-salons.yaml`, acknowledge the source policy, run
readiness, mark ready, and activate only after all required checks pass.

## 3. Controlled real-pilot sequence

Import or discover the first small batch (one query/location at a time), then
audit websites, score, generate briefs, and generate demos only for eligible
leads. Review every demo, create an expiring internal preview link, generate
the outreach draft, and approve readiness. Any manual contact occurs outside
LBOE. Afterwards log the operator assertion and record replies or meetings as
CRM events. Do not submit forms or send from the system.

## 4. Close and learn

Generate the export pack from `/ui/pilots/{id}/exports`, inspect the five
sanitized files, complete the retrospective, and close the pilot. Verify
`system_delivery_count` is zero in the pilot report.

Troubleshooting: rerun migrations for missing relations, use only
`--reset-synthetic` for rehearsal cleanup, and keep scraper/audit flags off
until the operator has reviewed the source policy and caps.
