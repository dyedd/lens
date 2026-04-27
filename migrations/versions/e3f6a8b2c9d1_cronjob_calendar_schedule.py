"""cron job calendar schedule

Revision ID: e3f6a8b2c9d1
Revises: d8a0e5c7f2b4
Create Date: 2026-04-26 00:00:01.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f6a8b2c9d1"
down_revision: Union[str, Sequence[str], None] = "d8a0e5c7f2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_name() -> str:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    return "cronjobs" if "cronjobs" in tables else "scheduled_tasks"


def upgrade() -> None:
    table_name = _table_name()
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(
            sa.Column(
                "schedule_type",
                sa.String(length=16),
                nullable=False,
                server_default="interval",
            )
        )
        batch_op.add_column(sa.Column("run_at_time", sa.String(length=5), nullable=True))
        batch_op.add_column(
            sa.Column(
                "weekdays_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column("schedule_type", server_default=None)
        batch_op.alter_column("weekdays_json", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table(_table_name()) as batch_op:
        batch_op.drop_column("weekdays_json")
        batch_op.drop_column("run_at_time")
        batch_op.drop_column("schedule_type")
