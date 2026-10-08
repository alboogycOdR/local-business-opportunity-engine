#!/usr/bin/env bash
# Restart the lab server for <db> on <port>, tracking it by PID file.
set -euo pipefail
DB="$1"; PORT="$2"; LAB="${LAB_DIR:-/tmp/claude-0/lab}"; PIDFILE="$LAB/uvicorn$PORT.pid"
[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
pgrep -f "uvicorn lboe_api.main:app --host 127.0.0.1 --port $PORT" | xargs -r kill 2>/dev/null || true
sleep 1
nohup "$(dirname "$0")/serve.sh" "$DB" "$PORT" > "$LAB/uvicorn$PORT.log" 2>&1 &
echo $! > "$PIDFILE"
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/health" && exit 0; sleep 0.25; done
echo "server did not start" >&2; exit 1
