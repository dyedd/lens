"""Move model sync settings to sites and flag models missing upstream.

Revision ID: a9d3f7c1e5b2
Revises: d4e5f6a7b8c9
Create Date: 2026-09-25
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "a9d3f7c1e5b2"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.add_column(
            sa.Column(
                "model_sync_enabled", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column(
                "model_sync_include",
                sa.Text(),
                nullable=False,
                server_default=sa.text("''"),
            )
        )
        batch.add_column(
            sa.Column(
                "model_sync_exclude",
                sa.Text(),
                nullable=False,
                server_default=sa.text("''"),
            )
        )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.add_column(
            sa.Column(
                "upstream_missing", sa.Integer(), nullable=False, server_default="0"
            )
        )

    conn = op.get_bind()
    sync_settings: dict[str, tuple[bool, str]] = {}
    for row in conn.execute(
        sa.text(
            "SELECT site_id, auto_sync_supported_models, auto_sync_model_pattern "
            "FROM site_protocol_configs ORDER BY site_id, id"
        )
    ).mappings():
        site_id = str(row["site_id"])
        is_enabled, pattern = sync_settings.get(site_id, (False, ""))
        row_pattern = str(row["auto_sync_model_pattern"] or "").strip()
        if row["auto_sync_supported_models"]:
            is_enabled = True
            pattern = pattern or row_pattern
        sync_settings[site_id] = (is_enabled, pattern)
    for site_id, (is_enabled, pattern) in sync_settings.items():
        if not is_enabled:
            continue
        conn.execute(
            sa.text(
                "UPDATE sites SET model_sync_enabled = 1, "
                "model_sync_include = :pattern WHERE id = :id"
            ),
            {"pattern": pattern, "id": site_id},
        )

    op.drop_table("site_protocol_config_sync_targets")
    with op.batch_alter_table("site_protocol_configs") as batch:
        batch.drop_column("auto_sync_model_pattern")
        batch.drop_column("auto_sync_supported_models")

    # Per-site switches only take effect while the shared cronjob runs.
    conn.execute(
        sa.text(
            "UPDATE cronjobs SET enabled = 1, status = 'idle', next_run_at = :now "
            "WHERE id = 'channel_model_sync' AND enabled = 0"
        ),
        {"now": datetime.now(UTC).replace(tzinfo=None)},
    )


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch:
        batch.add_column(
            sa.Column(
                "auto_sync_supported_models",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column(
                "auto_sync_model_pattern",
                sa.Text(),
                nullable=False,
                server_default=sa.text("''"),
            )
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
    op.execute(
        "UPDATE site_protocol_configs SET auto_sync_supported_models = 1, "
        "auto_sync_model_pattern = (SELECT sites.model_sync_include FROM sites "
        "WHERE sites.id = site_protocol_configs.site_id) "
        "WHERE site_id IN (SELECT id FROM sites WHERE model_sync_enabled = 1)"
    )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.drop_column("upstream_missing")
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_exclude")
        batch.drop_column("model_sync_include")
        batch.drop_column("model_sync_enabled")
