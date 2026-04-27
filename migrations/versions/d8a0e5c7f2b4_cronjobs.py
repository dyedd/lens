"""cron jobs

Revision ID: d8a0e5c7f2b4
Revises: c6b2d8e9f4a1
Create Date: 2026-04-26 00:00:00.000000

"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8a0e5c7f2b4"
down_revision: Union[str, Sequence[str], None] = "c6b2d8e9f4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cronjobs",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("interval_hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("lease_owner", sa.String(length=80), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cronjobs") as batch_op:
        batch_op.create_index(batch_op.f("ix_cronjobs_lease_owner"), ["lease_owner"], unique=False)
        batch_op.create_index(batch_op.f("ix_cronjobs_lease_until"), ["lease_until"], unique=False)
        batch_op.create_index(batch_op.f("ix_cronjobs_next_run_at"), ["next_run_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_cronjobs_status"), ["status"], unique=False)

    now = datetime.utcnow()
    cronjobs = sa.table(
        "cronjobs",
        sa.column("id", sa.String),
        sa.column("enabled", sa.Integer),
        sa.column("interval_hours", sa.Integer),
        sa.column("status", sa.String),
        sa.column("last_error", sa.Text),
        sa.column("next_run_at", sa.DateTime),
        sa.column("lease_owner", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.get_bind().execute(
        cronjobs.insert(),
        [
            {
                "id": "request_log_prune",
                "enabled": 1,
                "interval_hours": 1,
                "status": "idle",
                "last_error": "",
                "next_run_at": now,
                "lease_owner": "",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "model_price_sync",
                "enabled": 1,
                "interval_hours": 24,
                "status": "idle",
                "last_error": "",
                "next_run_at": now,
                "lease_owner": "",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "cronjobs" in tables:
        op.drop_table("cronjobs")
    elif "scheduled_tasks" in tables:
        op.drop_table("scheduled_tasks")
