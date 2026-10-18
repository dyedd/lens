#!/bin/sh
set -eu

mkdir -p /app/data

# Upgrades the schema and writes the initial admin password when needed.
if [ "${LENS_SKIP_DB_UPGRADE:-0}" = "1" ]; then
  echo "LENS_SKIP_DB_UPGRADE=1: skipping the startup migration" >&2
else
  lens migrate
fi

exec lens serve --host 0.0.0.0 --port "${LENS_PORT:-3000}"
