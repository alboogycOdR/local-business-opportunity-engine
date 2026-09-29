#!/usr/bin/env bash
# Find the concurrency at which UI requests wedge the connection pool (WS-P/WS-J).
set -uo pipefail
cd "$(dirname "$0")/../.."
export PATH="$PWD/.venv-audit/bin:$PATH"
DB="${1:-lboe_s100}"; BIZ="$2"; OUT="${OUT:-audit/evidence/perf/pool_threshold.txt}"; LEVELS="${LEVELS:-1 5 10 15 16 20 30}"; REQUESTS="${REQUESTS:-60}"
for c in $LEVELS; do
  audit/lab/restart.sh "$DB" 8001 >/dev/null
  r=$(timeout 200 python audit/lab/load_test.py --base http://127.0.0.1:8001 --path "/ui/businesses/$BIZ" \
      --requests "$REQUESTS" --concurrency "$c" --timeout 45 --db "$DB" --out audit/evidence/perf/load_ui_threshold.json 2>/dev/null \
      | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['statuses'],'p95_ms',d['p95_ms'],'peak_conn',d['pg_connections_peak'])" 2>/dev/null \
      || echo "load run exceeded 200s")
  sleep 3
  after=$(curl -s -o /dev/null -m 35 -w "%{http_code}" "http://127.0.0.1:8001/v1/businesses/$BIZ")
  stuck=$(PGPASSWORD=lboe_dev_only psql -h localhost -U lboe -d lboe -tAc \
      "select count(*) from pg_stat_activity where datname='$DB' and state='idle in transaction'")
  echo "code=${APP_ROOT:-baseline} requests=$REQUESTS concurrency=$c | $r | API afterwards=$after | idle-in-transaction=$stuck" | tee -a "$OUT"
done
