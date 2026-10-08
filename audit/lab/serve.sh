#!/usr/bin/env bash
# Start the LBOE API against an audit database: [APP_ROOT=<checkout>] audit/lab/serve.sh <db> <port> [extra env...]
# The repository is not installable (pip install -e . fails), so PYTHONPATH mirrors the Dockerfile.
set -euo pipefail
DB="$1"; PORT="$2"; shift 2
AUDIT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT="${APP_ROOT:-$AUDIT_ROOT}"   # code under test; defaults to this checkout
LAB="${LAB_DIR:-/tmp/claude-0/lab}"
SCALE="${DB#lboe_s}"
export PYTHONPATH="$ROOT/apps/api/src:$ROOT/packages/domain/src:$ROOT/packages/scoring/src:$ROOT/integrations/maps_scraper/src:$ROOT/integrations/website_auditor/src"
export LBOE_DATABASE_URL="postgresql+psycopg://lboe:${PGPASSWORD:-lboe_dev_only}@localhost:5432/$DB"
export LBOE_DEMO_ARTIFACT_ROOT="$LAB/art$SCALE" LBOE_EXPORT_ROOT="$LAB/exp$SCALE"
cd "$ROOT"   # StaticFiles directory is CWD-relative (lead L11)
exec env "$@" "$AUDIT_ROOT/.venv-audit/bin/uvicorn" lboe_api.main:app --host 127.0.0.1 --port "$PORT" --log-level warning
