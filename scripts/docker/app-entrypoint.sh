#!/usr/bin/env bash
set -euo pipefail

if [ "${LENS_SKIP_DB_UPGRADE:-0}" != "1" ]; then
  python -m lens_api.cli db upgrade
fi

python -m lens_api.cli serve &
backend_pid=$!

cd /app/ui
node server.js &
frontend_pid=$!

shutdown() {
  kill -TERM "$backend_pid" "$frontend_pid" 2>/dev/null || true
  wait "$backend_pid" 2>/dev/null || true
  wait "$frontend_pid" 2>/dev/null || true
}

trap shutdown INT TERM

wait -n "$backend_pid" "$frontend_pid"
status=$?
shutdown
exit "$status"
