"""cache token daily stats

Revision ID: c6b2d8e9f4a1
Revises: b4c1e9d2a6f7
Create Date: 2026-04-23 18:35:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6b2d8e9f4a1"
down_revision: Union[str, Sequence[str], None] = "b4c1e9d2a6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("request_log_daily_stats") as batch_op:
        batch_op.add_column(
            sa.Column(
                "cache_read_input_tokens",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "cache_write_input_tokens",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    with op.batch_alter_table("request_log_daily_stats") as batch_op:
        batch_op.alter_column("cache_read_input_tokens", server_default=None)
        batch_op.alter_column("cache_write_input_tokens", server_default=None)

    op.execute(
        """
        UPDATE request_log_daily_stats
        SET
            cache_read_input_tokens = COALESCE((
                SELECT SUM(request_logs.cache_read_input_tokens)
                FROM request_logs
                WHERE request_logs.stats_archived = 1
                  AND strftime('%Y%m%d', request_logs.created_at) = request_log_daily_stats.date
            ), 0),
            cache_write_input_tokens = COALESCE((
                SELECT SUM(request_logs.cache_write_input_tokens)
                FROM request_logs
                WHERE request_logs.stats_archived = 1
                  AND strftime('%Y%m%d', request_logs.created_at) = request_log_daily_stats.date
            ), 0)
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("request_log_daily_stats") as batch_op:
        batch_op.drop_column("cache_write_input_tokens")
        batch_op.drop_column("cache_read_input_tokens")
