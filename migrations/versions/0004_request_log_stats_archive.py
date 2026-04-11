"""add request log stats archive

Revision ID: 0004_request_log_stats_archive
Revises: 0003
Create Date: 2026-04-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_request_log_stats_archive"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("stats_archived", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "request_log_daily_stats",
        sa.Column("date", sa.String(8), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wait_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("output_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.PrimaryKeyConstraint("date"),
    )
    op.create_table(
        "overview_model_daily_stats",
        sa.Column("date", sa.String(8), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.PrimaryKeyConstraint("date", "model"),
    )
    op.create_index(
        "ix_overview_model_daily_stats_model",
        "overview_model_daily_stats",
        ["model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_overview_model_daily_stats_model", table_name="overview_model_daily_stats")
    op.drop_table("overview_model_daily_stats")
    op.drop_table("request_log_daily_stats")
    op.drop_column("request_logs", "stats_archived")
