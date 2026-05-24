"""site protocol credential id

Revision ID: d1e2f3a4b5c6
Revises: b9d4e7a1c6f2
Create Date: 2026-05-23 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "b9d4e7a1c6f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "credential_id",
                sa.String(length=80),
                nullable=False,
                server_default="",
            )
        )

    bind.execute(
        sa.text("""
            UPDATE site_protocol_configs
            SET credential_id = (
                SELECT credential_id
                FROM site_protocol_credential_bindings
                WHERE protocol_config_id = site_protocol_configs.id
                ORDER BY enabled DESC, sort_order ASC, id ASC
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1
                FROM site_protocol_credential_bindings
                WHERE protocol_config_id = site_protocol_configs.id
            )
            """)
    )

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.alter_column("credential_id", server_default=None)
        batch_op.create_index(
            batch_op.f("ix_site_protocol_configs_credential_id"),
            ["credential_id"],
            unique=False,
        )

    default_columns = {
        "model_group_items": [
            ("credential_id", sa.String(length=80)),
            ("enabled", sa.Integer()),
            ("sort_order", sa.Integer()),
        ],
        "model_groups": [("route_group_id", sa.String(length=80))],
        "overview_model_daily_stats": [
            ("requests", sa.Integer()),
            ("total_tokens", sa.Integer()),
            ("total_cost_usd", sa.Float()),
        ],
        "request_log_daily_stats": [
            ("request_count", sa.Integer()),
            ("successful_requests", sa.Integer()),
            ("failed_requests", sa.Integer()),
            ("wait_time_ms", sa.Integer()),
            ("input_tokens", sa.Integer()),
            ("cache_read_input_tokens", sa.Integer()),
            ("cache_write_input_tokens", sa.Integer()),
            ("output_tokens", sa.Integer()),
            ("total_tokens", sa.Integer()),
            ("input_cost_usd", sa.Float()),
            ("output_cost_usd", sa.Float()),
            ("total_cost_usd", sa.Float()),
        ],
        "request_logs": [
            ("lifecycle_status", sa.String(length=32)),
            ("is_stream", sa.Integer()),
            ("first_token_latency_ms", sa.Integer()),
            ("input_tokens", sa.Integer()),
            ("cache_read_input_tokens", sa.Integer()),
            ("cache_write_input_tokens", sa.Integer()),
            ("output_tokens", sa.Integer()),
            ("total_tokens", sa.Integer()),
            ("input_cost_usd", sa.Float()),
            ("output_cost_usd", sa.Float()),
            ("total_cost_usd", sa.Float()),
            ("attempts_json", sa.Text()),
            ("stats_archived", sa.Integer()),
        ],
        "site_base_urls": [
            ("name", sa.String(length=120)),
            ("enabled", sa.Integer()),
            ("sort_order", sa.Integer()),
        ],
        "site_credentials": [
            ("enabled", sa.Integer()),
            ("sort_order", sa.Integer()),
        ],
        "site_discovered_models": [
            ("enabled", sa.Integer()),
            ("sort_order", sa.Integer()),
        ],
        "site_protocol_configs": [
            ("enabled", sa.Integer()),
            ("headers_json", sa.Text()),
            ("channel_proxy", sa.Text()),
            ("param_override", sa.Text()),
            ("match_regex", sa.Text()),
            ("base_url_id", sa.String(length=80)),
        ],
    }

    for table_name, columns in default_columns.items():
        columns_by_name = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        changed_columns = [
            (column_name, column_type)
            for column_name, column_type in columns
            if columns_by_name[column_name].get("default") is not None
        ]
        if changed_columns:
            with op.batch_alter_table(table_name) as batch_op:
                for column_name, column_type in changed_columns:
                    batch_op.alter_column(
                        column_name,
                        existing_type=column_type,
                        existing_nullable=False,
                        server_default=None,
                    )

    price_columns = {
        column["name"]: column for column in inspector.get_columns("model_prices")
    }
    changed_price_columns = []
    for column_name in (
        "cache_read_price_per_million",
        "cache_write_price_per_million",
    ):
        column = price_columns[column_name]
        column_type = str(column["type"]).upper()
        if column.get("default") is not None or column_type == "REAL":
            changed_price_columns.append((column_name, column["type"]))
    if changed_price_columns:
        with op.batch_alter_table("model_prices") as batch_op:
            for column_name, existing_type in changed_price_columns:
                batch_op.alter_column(
                    column_name,
                    existing_type=existing_type,
                    type_=sa.Float(),
                    existing_nullable=False,
                    server_default=None,
                )

    index_names = {
        index["name"]
        for index in inspector.get_indexes("overview_model_daily_stats")
    }
    if "ix_overview_model_daily_stats_model" in index_names:
        op.drop_index(
            "ix_overview_model_daily_stats_model",
            table_name="overview_model_daily_stats",
        )

    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.create_check_constraint(
            "ck_model_group_items_credential_id_not_empty",
            "credential_id <> ''",
        )

    op.drop_table("site_protocol_credential_bindings")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
