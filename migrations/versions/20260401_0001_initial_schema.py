"""initial schema

Revision ID: 20260401_0001
Revises:
Create Date: 2026-04-01 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260401_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_users_username"), "admin_users", ["username"], unique=True)

    op.create_table(
        "providers",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("headers_json", sa.Text(), nullable=False),
        sa.Column("model_patterns_json", sa.Text(), nullable=False),
        sa.Column("base_urls_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("keys_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("proxy", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channel_proxy", sa.Text(), nullable=False, server_default=""),
        sa.Column("param_override", sa.Text(), nullable=False, server_default=""),
        sa.Column("match_regex", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_providers_protocol", "providers", ["protocol"], unique=False)

    op.create_table(
        "model_groups",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("provider_ids_json", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_groups_name"), "model_groups", ["name"], unique=True)
    op.create_index(op.f("ix_model_groups_protocol"), "model_groups", ["protocol"], unique=False)

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "request_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("requested_model", sa.String(length=200), nullable=True),
        sa.Column("matched_group_name", sa.String(length=120), nullable=True),
        sa.Column("provider_id", sa.String(length=80), nullable=True),
        sa.Column("gateway_key_id", sa.String(length=80), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("success", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("resolved_model", sa.String(length=200), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("output_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_request_logs_created_at"), "request_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_request_logs_gateway_key_id"), "request_logs", ["gateway_key_id"], unique=False)
    op.create_index(op.f("ix_request_logs_protocol"), "request_logs", ["protocol"], unique=False)
    op.create_index(op.f("ix_request_logs_provider_id"), "request_logs", ["provider_id"], unique=False)
    op.create_index(op.f("ix_request_logs_resolved_model"), "request_logs", ["resolved_model"], unique=False)

    op.create_table(
        "model_prices",
        sa.Column("model_key", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("input_price_per_million", sa.Float(), nullable=False),
        sa.Column("output_price_per_million", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("model_key"),
    )

    op.create_table(
        "imported_stats_total",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("input_token", sa.Integer(), nullable=False),
        sa.Column("output_token", sa.Integer(), nullable=False),
        sa.Column("input_cost", sa.Float(), nullable=False),
        sa.Column("output_cost", sa.Float(), nullable=False),
        sa.Column("wait_time", sa.Integer(), nullable=False),
        sa.Column("request_success", sa.Integer(), nullable=False),
        sa.Column("request_failed", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "imported_stats_daily",
        sa.Column("date", sa.String(length=8), nullable=False),
        sa.Column("input_token", sa.Integer(), nullable=False),
        sa.Column("output_token", sa.Integer(), nullable=False),
        sa.Column("input_cost", sa.Float(), nullable=False),
        sa.Column("output_cost", sa.Float(), nullable=False),
        sa.Column("wait_time", sa.Integer(), nullable=False),
        sa.Column("request_success", sa.Integer(), nullable=False),
        sa.Column("request_failed", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("date"),
    )


def downgrade() -> None:
    op.drop_table("imported_stats_daily")
    op.drop_table("imported_stats_total")
    op.drop_table("model_prices")
    op.drop_index(op.f("ix_request_logs_resolved_model"), table_name="request_logs")
    op.drop_index(op.f("ix_request_logs_provider_id"), table_name="request_logs")
    op.drop_index(op.f("ix_request_logs_protocol"), table_name="request_logs")
    op.drop_index(op.f("ix_request_logs_gateway_key_id"), table_name="request_logs")
    op.drop_index(op.f("ix_request_logs_created_at"), table_name="request_logs")
    op.drop_table("request_logs")
    op.drop_table("settings")
    op.drop_index(op.f("ix_model_groups_protocol"), table_name="model_groups")
    op.drop_index(op.f("ix_model_groups_name"), table_name="model_groups")
    op.drop_table("model_groups")
    op.drop_index("ix_providers_protocol", table_name="providers")
    op.drop_table("providers")
    op.drop_index(op.f("ix_admin_users_username"), table_name="admin_users")
    op.drop_table("admin_users")

