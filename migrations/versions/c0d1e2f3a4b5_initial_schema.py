"""Initial schema through the site tags migration."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("username", sa.VARCHAR(length=80), nullable=False),
        sa.Column("password_hash", sa.TEXT(), nullable=False),
        sa.Column("is_active", sa.INTEGER(), nullable=False),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.Column("updated_at", sa.DATETIME(), nullable=False),
        sa.Column("auth_token_version", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=1)
    op.create_table(
        "cronjobs",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("interval_hours", sa.INTEGER(), nullable=False),
        sa.Column("status", sa.VARCHAR(length=32), nullable=False),
        sa.Column("last_started_at", sa.DATETIME(), nullable=True),
        sa.Column("last_finished_at", sa.DATETIME(), nullable=True),
        sa.Column("last_error", sa.TEXT(), nullable=False),
        sa.Column("next_run_at", sa.DATETIME(), nullable=True),
        sa.Column("lease_owner", sa.VARCHAR(length=80), nullable=False),
        sa.Column("lease_until", sa.DATETIME(), nullable=True),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.Column("updated_at", sa.DATETIME(), nullable=False),
        sa.Column("schedule_type", sa.VARCHAR(length=16), nullable=False),
        sa.Column("run_at_time", sa.VARCHAR(length=5), nullable=True),
        sa.Column("weekdays_json", sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cronjobs_lease_owner", "cronjobs", ["lease_owner"], unique=False
    )
    op.create_index(
        "ix_cronjobs_lease_until", "cronjobs", ["lease_until"], unique=False
    )
    op.create_index(
        "ix_cronjobs_next_run_at", "cronjobs", ["next_run_at"], unique=False
    )
    op.create_index("ix_cronjobs_status", "cronjobs", ["status"], unique=False)
    op.create_table(
        "gateway_api_keys",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("remark", sa.VARCHAR(length=120), nullable=False),
        sa.Column("api_key", sa.TEXT(), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("allowed_models_json", sa.TEXT(), nullable=False),
        sa.Column("max_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("expires_at", sa.DATETIME(), nullable=True),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.Column("updated_at", sa.DATETIME(), nullable=False),
        sa.Column("spent_cost_usd", sa.FLOAT(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key"),
    )
    op.create_table(
        "imported_stats_daily",
        sa.Column("date", sa.VARCHAR(length=8), nullable=False),
        sa.Column("input_token", sa.INTEGER(), nullable=False),
        sa.Column("output_token", sa.INTEGER(), nullable=False),
        sa.Column("input_cost", sa.FLOAT(), nullable=False),
        sa.Column("output_cost", sa.FLOAT(), nullable=False),
        sa.Column("wait_time", sa.INTEGER(), nullable=False),
        sa.Column("request_success", sa.INTEGER(), nullable=False),
        sa.Column("request_failed", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("date"),
    )
    op.create_table(
        "imported_stats_total",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("input_token", sa.INTEGER(), nullable=False),
        sa.Column("output_token", sa.INTEGER(), nullable=False),
        sa.Column("input_cost", sa.FLOAT(), nullable=False),
        sa.Column("output_cost", sa.FLOAT(), nullable=False),
        sa.Column("wait_time", sa.INTEGER(), nullable=False),
        sa.Column("request_success", sa.INTEGER(), nullable=False),
        sa.Column("request_failed", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_group_items",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("group_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("channel_id", sa.VARCHAR(length=160), nullable=False),
        sa.Column("credential_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("model_name", sa.VARCHAR(length=200), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("sort_order", sa.INTEGER(), nullable=False),
        sa.CheckConstraint(
            "credential_id <> ''", name="ck_model_group_items_credential_id_not_empty"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_id",
            "channel_id",
            "credential_id",
            "model_name",
            name="uq_model_group_items_target",
        ),
    )
    op.create_index(
        "ix_model_group_items_channel_id",
        "model_group_items",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_group_items_credential_id",
        "model_group_items",
        ["credential_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_group_items_group_id", "model_group_items", ["group_id"], unique=False
    )
    op.create_table(
        "model_groups",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), nullable=False),
        sa.Column("strategy", sa.VARCHAR(length=32), nullable=False),
        sa.Column("route_group_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("sync_filter_mode", sa.VARCHAR(length=20), nullable=False),
        sa.Column("sync_filter_query", sa.TEXT(), nullable=False),
        sa.Column(
            "protocols_json", sa.TEXT(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.CheckConstraint(
            "sync_filter_mode IN ('', 'contains', 'regex')",
            name="ck_model_groups_sync_filter_mode",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_groups_name", "model_groups", ["name"], unique=1)
    op.create_index(
        "ix_model_groups_route_group_id",
        "model_groups",
        ["route_group_id"],
        unique=False,
    )
    op.create_table(
        "model_prices",
        sa.Column("model_key", sa.VARCHAR(length=200), nullable=False),
        sa.Column("display_name", sa.VARCHAR(length=200), nullable=False),
        sa.Column("input_price_per_million", sa.FLOAT(), nullable=False),
        sa.Column("output_price_per_million", sa.FLOAT(), nullable=False),
        sa.Column("cache_read_price_per_million", sa.FLOAT(), nullable=False),
        sa.Column("cache_write_price_per_million", sa.FLOAT(), nullable=False),
        sa.PrimaryKeyConstraint("model_key"),
    )
    op.create_table(
        "overview_model_daily_stats",
        sa.Column("date", sa.VARCHAR(length=8), nullable=False),
        sa.Column("model", sa.VARCHAR(length=200), nullable=False),
        sa.Column("requests", sa.INTEGER(), nullable=False),
        sa.Column("total_tokens", sa.INTEGER(), nullable=False),
        sa.Column("total_cost_usd", sa.FLOAT(), nullable=False),
        sa.PrimaryKeyConstraint("date", "model"),
    )
    op.create_table(
        "request_log_daily_stats",
        sa.Column("date", sa.VARCHAR(length=8), nullable=False),
        sa.Column("request_count", sa.INTEGER(), nullable=False),
        sa.Column("successful_requests", sa.INTEGER(), nullable=False),
        sa.Column("failed_requests", sa.INTEGER(), nullable=False),
        sa.Column("wait_time_ms", sa.INTEGER(), nullable=False),
        sa.Column("input_tokens", sa.INTEGER(), nullable=False),
        sa.Column("output_tokens", sa.INTEGER(), nullable=False),
        sa.Column("total_tokens", sa.INTEGER(), nullable=False),
        sa.Column("input_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("output_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("total_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("cache_read_input_tokens", sa.INTEGER(), nullable=False),
        sa.Column("cache_write_input_tokens", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("date"),
    )
    op.create_table(
        "request_logs",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("protocol", sa.VARCHAR(length=40), nullable=False),
        sa.Column("requested_group_name", sa.VARCHAR(length=120), nullable=True),
        sa.Column("resolved_group_name", sa.VARCHAR(length=120), nullable=True),
        sa.Column("upstream_model_name", sa.VARCHAR(length=200), nullable=True),
        sa.Column("channel_id", sa.VARCHAR(length=160), nullable=True),
        sa.Column("channel_name", sa.VARCHAR(length=120), nullable=True),
        sa.Column("gateway_key_id", sa.VARCHAR(length=80), nullable=True),
        sa.Column("status_code", sa.INTEGER(), nullable=True),
        sa.Column("success", sa.INTEGER(), nullable=False),
        sa.Column("is_stream", sa.INTEGER(), nullable=False),
        sa.Column("first_token_latency_ms", sa.INTEGER(), nullable=False),
        sa.Column("latency_ms", sa.INTEGER(), nullable=False),
        sa.Column("input_tokens", sa.INTEGER(), nullable=False),
        sa.Column("cache_read_input_tokens", sa.INTEGER(), nullable=False),
        sa.Column("cache_write_input_tokens", sa.INTEGER(), nullable=False),
        sa.Column("output_tokens", sa.INTEGER(), nullable=False),
        sa.Column("total_tokens", sa.INTEGER(), nullable=False),
        sa.Column("input_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("output_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("total_cost_usd", sa.FLOAT(), nullable=False),
        sa.Column("request_content", sa.TEXT(), nullable=True),
        sa.Column("response_content", sa.TEXT(), nullable=True),
        sa.Column("attempts_json", sa.TEXT(), nullable=False),
        sa.Column("error_message", sa.TEXT(), nullable=True),
        sa.Column("stats_archived", sa.INTEGER(), nullable=False),
        sa.Column("created_at", sa.DATETIME(), nullable=False),
        sa.Column("lifecycle_status", sa.VARCHAR(length=32), nullable=False),
        sa.Column("user_agent", sa.VARCHAR(length=300), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_request_logs_channel_id", "request_logs", ["channel_id"], unique=False
    )
    op.create_index(
        "ix_request_logs_created_at", "request_logs", ["created_at"], unique=False
    )
    op.create_index(
        "ix_request_logs_gateway_key_id",
        "request_logs",
        ["gateway_key_id"],
        unique=False,
    )
    op.create_index(
        "ix_request_logs_lifecycle_status",
        "request_logs",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_index(
        "ix_request_logs_protocol", "request_logs", ["protocol"], unique=False
    )
    op.create_index(
        "ix_request_logs_resolved_group_name",
        "request_logs",
        ["resolved_group_name"],
        unique=False,
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.VARCHAR(length=80), nullable=False),
        sa.Column("value", sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "site_base_urls",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("site_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("url", sa.VARCHAR(length=500), nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("sort_order", sa.INTEGER(), nullable=False),
        sa.Column(
            "supported_protocols_json",
            sa.TEXT(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_base_urls_site_id", "site_base_urls", ["site_id"], unique=False
    )
    op.create_table(
        "site_credentials",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("site_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), nullable=False),
        sa.Column("api_key", sa.TEXT(), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("sort_order", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_credentials_site_id", "site_credentials", ["site_id"], unique=False
    )
    op.create_table(
        "site_discovered_models",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("credential_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("model_name", sa.VARCHAR(length=200), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("sort_order", sa.INTEGER(), nullable=False),
        sa.Column("protocol", sa.VARCHAR(length=40), nullable=True),
        sa.Column("source", sa.VARCHAR(length=16), nullable=False),
        sa.CheckConstraint(
            "source IN ('manual', 'synced')", name="ck_site_discovered_models_source"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "protocol_config_id",
            "credential_id",
            "protocol",
            "model_name",
            name="uq_site_discovered_models_target",
        ),
    )
    op.create_index(
        "ix_site_discovered_models_credential_id",
        "site_discovered_models",
        ["credential_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_discovered_models_protocol_config_id",
        "site_discovered_models",
        ["protocol_config_id"],
        unique=False,
    )
    op.create_table(
        "site_protocol_config_credentials",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("credential_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("sort_order", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "protocol_config_id",
            "credential_id",
            name="uq_site_protocol_config_credentials_target",
        ),
    )
    op.create_index(
        "ix_site_protocol_config_credentials_credential_id",
        "site_protocol_config_credentials",
        ["credential_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_protocol_config_credentials_protocol_config_id",
        "site_protocol_config_credentials",
        ["protocol_config_id"],
        unique=False,
    )
    op.create_table(
        "site_protocol_config_sync_targets",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("credential_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("protocol", sa.VARCHAR(length=40), nullable=False),
        sa.Column("model_name", sa.VARCHAR(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "protocol_config_id",
            "credential_id",
            "protocol",
            "model_name",
            name="uq_site_protocol_config_sync_targets_target",
        ),
    )
    op.create_index(
        "ix_site_protocol_config_sync_targets_credential_id",
        "site_protocol_config_sync_targets",
        ["credential_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_protocol_config_sync_targets_protocol_config_id",
        "site_protocol_config_sync_targets",
        ["protocol_config_id"],
        unique=False,
    )
    op.create_table(
        "site_protocol_configs",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("site_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column("headers_json", sa.TEXT(), nullable=False),
        sa.Column("channel_proxy", sa.TEXT(), nullable=False),
        sa.Column("param_override", sa.TEXT(), nullable=False),
        sa.Column("base_url_id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), nullable=False),
        sa.Column(
            "protocols_json", sa.TEXT(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.Column("proxy_mode", sa.VARCHAR(length=16), nullable=False),
        sa.CheckConstraint(
            "base_url_id <> ''", name="ck_site_protocol_configs_base_url_id_not_empty"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_protocol_configs_site_id",
        "site_protocol_configs",
        ["site_id"],
        unique=False,
    )
    op.create_table(
        "sites",
        sa.Column("id", sa.VARCHAR(length=80), nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), nullable=False),
        sa.Column("enabled", sa.INTEGER(), nullable=False),
        sa.Column(
            "tags_json", sa.TEXT(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sites_name", "sites", ["name"], unique=1)


def downgrade() -> None:
    op.drop_index("ix_sites_name", table_name="sites")
    op.drop_table("sites")
    op.drop_index(
        "ix_site_protocol_configs_site_id", table_name="site_protocol_configs"
    )
    op.drop_table("site_protocol_configs")
    op.drop_index(
        "ix_site_protocol_config_sync_targets_protocol_config_id",
        table_name="site_protocol_config_sync_targets",
    )
    op.drop_index(
        "ix_site_protocol_config_sync_targets_credential_id",
        table_name="site_protocol_config_sync_targets",
    )
    op.drop_table("site_protocol_config_sync_targets")
    op.drop_index(
        "ix_site_protocol_config_credentials_protocol_config_id",
        table_name="site_protocol_config_credentials",
    )
    op.drop_index(
        "ix_site_protocol_config_credentials_credential_id",
        table_name="site_protocol_config_credentials",
    )
    op.drop_table("site_protocol_config_credentials")
    op.drop_index(
        "ix_site_discovered_models_protocol_config_id",
        table_name="site_discovered_models",
    )
    op.drop_index(
        "ix_site_discovered_models_credential_id", table_name="site_discovered_models"
    )
    op.drop_table("site_discovered_models")
    op.drop_index("ix_site_credentials_site_id", table_name="site_credentials")
    op.drop_table("site_credentials")
    op.drop_index("ix_site_base_urls_site_id", table_name="site_base_urls")
    op.drop_table("site_base_urls")
    op.drop_table("settings")
    op.drop_index("ix_request_logs_resolved_group_name", table_name="request_logs")
    op.drop_index("ix_request_logs_protocol", table_name="request_logs")
    op.drop_index("ix_request_logs_lifecycle_status", table_name="request_logs")
    op.drop_index("ix_request_logs_gateway_key_id", table_name="request_logs")
    op.drop_index("ix_request_logs_created_at", table_name="request_logs")
    op.drop_index("ix_request_logs_channel_id", table_name="request_logs")
    op.drop_table("request_logs")
    op.drop_table("request_log_daily_stats")
    op.drop_table("overview_model_daily_stats")
    op.drop_table("model_prices")
    op.drop_index("ix_model_groups_route_group_id", table_name="model_groups")
    op.drop_index("ix_model_groups_name", table_name="model_groups")
    op.drop_table("model_groups")
    op.drop_index("ix_model_group_items_group_id", table_name="model_group_items")
    op.drop_index("ix_model_group_items_credential_id", table_name="model_group_items")
    op.drop_index("ix_model_group_items_channel_id", table_name="model_group_items")
    op.drop_table("model_group_items")
    op.drop_table("imported_stats_total")
    op.drop_table("imported_stats_daily")
    op.drop_table("gateway_api_keys")
    op.drop_index("ix_cronjobs_status", table_name="cronjobs")
    op.drop_index("ix_cronjobs_next_run_at", table_name="cronjobs")
    op.drop_index("ix_cronjobs_lease_until", table_name="cronjobs")
    op.drop_index("ix_cronjobs_lease_owner", table_name="cronjobs")
    op.drop_table("cronjobs")
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
