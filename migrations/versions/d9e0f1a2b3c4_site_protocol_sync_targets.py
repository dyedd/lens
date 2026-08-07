"""replace protocol sync filters with exact model targets

Revision ID: d9e0f1a2b3c4
Revises: a4c7e2f9b1d6
Create Date: 2026-08-07 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "a4c7e2f9b1d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    op.execute("""
        INSERT INTO site_protocol_config_sync_targets
            (id, protocol_config_id, credential_id, protocol, model_name)
        SELECT id, protocol_config_id, credential_id, protocol, model_name
        FROM site_discovered_models
        WHERE source = 'synced'
        """)
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_column("match_regex")
        batch_op.drop_column("auto_sync_enabled")


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column("match_regex", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column(
                "auto_sync_enabled", sa.Integer(), nullable=False, server_default="0"
            )
        )
    op.execute("""
        UPDATE site_protocol_configs
        SET auto_sync_enabled = 1
        WHERE id IN (
            SELECT DISTINCT protocol_config_id
            FROM site_protocol_config_sync_targets
        )
        """)
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.alter_column("match_regex", server_default=None)
        batch_op.alter_column("auto_sync_enabled", server_default=None)
    op.drop_index(
        "ix_site_protocol_config_sync_targets_credential_id",
        table_name="site_protocol_config_sync_targets",
    )
    op.drop_index(
        "ix_site_protocol_config_sync_targets_protocol_config_id",
        table_name="site_protocol_config_sync_targets",
    )
    op.drop_table("site_protocol_config_sync_targets")
