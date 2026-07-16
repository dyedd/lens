#!/bin/sh
set -eu

mkdir -p /app/data

if [ "${LENS_SKIP_DB_UPGRADE:-0}" != "1" ]; then
  lens db upgrade
fi

lens seed-admin --username admin --password admin

exec lens serve --host 0.0.0.0 --port 3000 --ui-static-dir /app/ui
