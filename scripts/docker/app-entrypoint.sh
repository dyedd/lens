#!/bin/sh
set -eu

mkdir -p /app/data

if [ "${LENS_SKIP_DB_UPGRADE:-0}" != "1" ]; then
  lens db upgrade
fi

lens seed-admin --username admin --password admin

exec lens serve
