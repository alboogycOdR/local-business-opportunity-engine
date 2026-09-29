#!/usr/bin/env bash
# Recreate and migrate a scratch audit database: audit/lab/reset_db.sh lboe_s100
set -euo pipefail
DB="$1"
export PGPASSWORD="${PGPASSWORD:-lboe_dev_only}"
psql -h localhost -U lboe -d lboe -qc "drop database if exists $DB" -c "create database $DB" 2>/dev/null
"$(cd "$(dirname "$0")/../.." && pwd)/.venv-audit/bin/python" "${MIGRATE:-scripts/migrate.py}" --database-url "postgresql+psycopg://lboe:${PGPASSWORD}@localhost:5432/$DB" | head -1
