"""恢复显式的模型同步目标，并默认开启同步。

Revision ID: f7a8b9c0d1e2
Revises: d9f1b3c5e7a2
Create Date: 2026-10-15
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "d9f1b3c5e7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_protocol_config_sync_targets",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.String(length=80), nullable=False),
        sa.Column("credential_id", sa.String(length=80), nullable=False),
        sa.Column("protocol", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
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
        "ix_site_protocol_config_sync_targets_protocol_config_id",
        "site_protocol_config_sync_targets",
        ["protocol_config_id"],
    )
    op.create_index(
        "ix_site_protocol_config_sync_targets_credential_id",
        "site_protocol_config_sync_targets",
        ["credential_id"],
    )
    conn = op.get_bind()
    for row in conn.execute(
        sa.text(
            "SELECT protocol_config_id, credential_id, protocol, model_name "
            "FROM site_discovered_models WHERE source = 'synced'"
        )
    ).mappings():
        conn.execute(
            sa.text(
                "INSERT INTO site_protocol_config_sync_targets "
                "(id, protocol_config_id, credential_id, protocol, model_name) "
                "VALUES (:id, :protocol_config_id, :credential_id, :protocol, :model_name)"
            ),
            {"id": str(uuid.uuid4()), **dict(row)},
        )
    with op.batch_alter_table("sites") as batch:
        batch.alter_column("model_sync_enabled", server_default="1")


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.alter_column("model_sync_enabled", server_default="0")
    op.drop_index(
        "ix_site_protocol_config_sync_targets_credential_id",
        table_name="site_protocol_config_sync_targets",
    )
    op.drop_index(
        "ix_site_protocol_config_sync_targets_protocol_config_id",
        table_name="site_protocol_config_sync_targets",
    )
    op.drop_table("site_protocol_config_sync_targets")
