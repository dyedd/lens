"""cron job request log stats persist

Revision ID: c2d4e6f8a9b1
Revises: a1c9e2f4b6d8
Create Date: 2026-04-27 00:00:02.000000

"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d4e6f8a9b1"
down_revision: Union[str, Sequence[str], None] = "a1c9e2f4b6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "settings" in tables:
        op.execute(
            "DELETE FROM settings WHERE key IN ('stats_save_interval', 'stats_last_persist_at')"
        )

    if "cronjobs" not in tables:
        return

    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM cronjobs WHERE id = :task_id"),
        {"task_id": "request_log_stats_persist"},
    ).first()
    if existing is not None:
        return

    now = datetime.utcnow()
    cronjobs = sa.table(
        "cronjobs",
        sa.column("id", sa.String),
        sa.column("enabled", sa.Integer),
        sa.column("schedule_type", sa.String),
        sa.column("interval_hours", sa.Integer),
        sa.column("run_at_time", sa.String),
        sa.column("weekdays_json", sa.Text),
        sa.column("status", sa.String),
        sa.column("last_error", sa.Text),
        sa.column("next_run_at", sa.DateTime),
        sa.column("lease_owner", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    bind.execute(
        cronjobs.insert(),
        {
            "id": "request_log_stats_persist",
            "enabled": 1,
            "schedule_type": "interval",
            "interval_hours": 1,
            "run_at_time": None,
            "weekdays_json": "[]",
            "status": "idle",
            "last_error": "",
            "next_run_at": now,
            "lease_owner": "",
            "created_at": now,
            "updated_at": now,
        },
    )


def downgrade() -> None:
    if "cronjobs" in _tables():
        op.execute("DELETE FROM cronjobs WHERE id = 'request_log_stats_persist'")
