"""cron job interval hours

Revision ID: f4b7c9d2e1a3
Revises: e3f6a8b2c9d1
Create Date: 2026-04-27 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b7c9d2e1a3"
down_revision: Union[str, Sequence[str], None] = "e3f6a8b2c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_name() -> str:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    return "cronjobs" if "cronjobs" in tables else "scheduled_tasks"


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    table_name = _table_name()
    columns = _columns(table_name)
    if "interval_hours" in columns and "interval_seconds" not in columns:
        return

    if "interval_hours" not in columns:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column("interval_hours", sa.Integer(), nullable=False, server_default="1")
            )

    op.execute(
        f"""
        UPDATE {table_name}
        SET interval_hours = CASE
            WHEN interval_seconds IS NULL OR interval_seconds < 3600 THEN 1
            ELSE (interval_seconds + 3599) / 3600
        END
        """
    )

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column("interval_seconds")
        batch_op.alter_column("interval_hours", server_default=None)


def downgrade() -> None:
    table_name = _table_name()
    columns = _columns(table_name)
    if "interval_seconds" in columns and "interval_hours" not in columns:
        return

    if "interval_seconds" not in columns:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="3600")
            )

    op.execute(
        f"""
        UPDATE {table_name}
        SET interval_seconds = interval_hours * 3600
        """
    )

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column("interval_hours")
        batch_op.alter_column("interval_seconds", server_default=None)
