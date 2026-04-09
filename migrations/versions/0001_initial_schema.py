"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(80), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "sites",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True, index=True),
        sa.Column("base_url", sa.String(500), nullable=False, server_default=""),
    )

    op.create_table(
        "site_credentials",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("site_id", sa.String(80), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("api_key", sa.Text, nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "site_protocol_configs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("site_id", sa.String(80), nullable=False, index=True),
        sa.Column("protocol", sa.String(40), nullable=False, index=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("headers_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("channel_proxy", sa.Text, nullable=False, server_default=""),
        sa.Column("param_override", sa.Text, nullable=False, server_default=""),
        sa.Column("match_regex", sa.Text, nullable=False, server_default=""),
    )

    op.create_table(
        "site_protocol_credential_bindings",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("protocol_config_id", sa.String(80), nullable=False, index=True),
        sa.Column("credential_id", sa.String(80), nullable=False, index=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "site_discovered_models",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("protocol_config_id", sa.String(80), nullable=False, index=True),
        sa.Column("credential_id", sa.String(80), nullable=False, index=True),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "model_groups",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, index=True),
        sa.Column("protocol", sa.String(40), nullable=False, index=True),
        sa.Column("strategy", sa.String(32), nullable=False, server_default="round_robin"),
        sa.Column("match_regex", sa.Text, nullable=False, server_default=""),
    )

    op.create_table(
        "model_group_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.String(80), nullable=False, index=True),
        sa.Column("channel_id", sa.String(80), nullable=False, index=True),
        sa.Column("credential_id", sa.String(80), nullable=False, server_default="", index=True),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )

    op.create_table(
        "request_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("protocol", sa.String(40), nullable=False, index=True),
        sa.Column("requested_model", sa.String(200), nullable=True),
        sa.Column("matched_group_name", sa.String(120), nullable=True),
        sa.Column("channel_id", sa.String(80), nullable=True, index=True),
        sa.Column("channel_name", sa.String(120), nullable=True),
        sa.Column("gateway_key_id", sa.String(80), nullable=True, index=True),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("success", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_stream", sa.Integer, nullable=False, server_default="0"),
        sa.Column("first_token_latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resolved_model", sa.String(200), nullable=True, index=True),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("output_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("request_content", sa.Text, nullable=True),
        sa.Column("response_content", sa.Text, nullable=True),
        sa.Column("attempts_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, index=True),
    )

    op.create_table(
        "model_prices",
        sa.Column("model_key", sa.String(200), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("input_price_per_million", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("output_price_per_million", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("cache_read_price_per_million", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("cache_write_price_per_million", sa.Float, nullable=False, server_default="0.0"),
    )

    op.create_table(
        "imported_stats_total",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("input_token", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_token", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("output_cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("wait_time", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_success", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_failed", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "imported_stats_daily",
        sa.Column("date", sa.String(8), primary_key=True),
        sa.Column("input_token", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_token", sa.Integer, nullable=False, server_default="0"),
        sa.Column("input_cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("output_cost", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("wait_time", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_success", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_failed", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("imported_stats_daily")
    op.drop_table("imported_stats_total")
    op.drop_table("model_prices")
    op.drop_table("request_logs")
    op.drop_table("settings")
    op.drop_table("model_group_items")
    op.drop_table("model_groups")
    op.drop_table("site_discovered_models")
    op.drop_table("site_protocol_credential_bindings")
    op.drop_table("site_protocol_configs")
    op.drop_table("site_credentials")
    op.drop_table("sites")
    op.drop_table("admin_users")
