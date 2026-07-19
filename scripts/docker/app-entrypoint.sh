#!/bin/sh
set -eu

mkdir -p /app/data

if [ "${LENS_SKIP_DB_UPGRADE:-0}" != "1" ]; then
  lens db upgrade
fi

lens seed-admin \
  --username admin \
  --generate-password \
  --password-file /app/data/admin-password

exec lens serve --host 0.0.0.0 --port "${LENS_PORT:-3000}" --ui-static-dir /app/ui
