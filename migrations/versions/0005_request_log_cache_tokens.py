"""add request log cache token fields

Revision ID: 0005_request_log_cache_tokens
Revises: 0004_request_log_stats_archive
Create Date: 2026-04-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_request_log_cache_tokens"
down_revision = "0004_request_log_stats_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("cache_read_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "request_logs",
        sa.Column("cache_write_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "cache_write_input_tokens")
    op.drop_column("request_logs", "cache_read_input_tokens")
