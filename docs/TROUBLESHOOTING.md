# Troubleshooting

Check `/ready` first. Verify `LBOE_DATABASE_URL`, Redis, migrations, writable `artifacts/`/`exports/`, and `PYTHONPATH` for local uvicorn. Rerun `scripts/seed_pilot.py --reset-synthetic` only for synthetic pilot records. Never fix a production issue by storing credentials or bypassing safety gates.
