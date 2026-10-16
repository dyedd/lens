"""Make every configured site model an upstream sync target.

Revision ID: b2c4d6e8f0a1
Revises: a1b2c3d4e5f6
Create Date: 2026-10-16
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c4d6e8f0a1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    model_rows = conn.execute(
        sa.text(
            "SELECT protocol_config_id, credential_id, protocol, model_name "
            "FROM site_discovered_models"
        )
    ).mappings()
    for row in model_rows:
        conn.execute(
            sa.text(
                "INSERT INTO site_protocol_config_sync_targets "
                "(id, protocol_config_id, credential_id, protocol, model_name) "
                "SELECT :id, :protocol_config_id, :credential_id, :protocol, :model_name "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM site_protocol_config_sync_targets AS target "
                "WHERE target.protocol_config_id = :protocol_config_id "
                "AND target.credential_id = :credential_id "
                "AND target.protocol = :protocol "
                "AND target.model_name = :model_name)"
            ),
            {"id": str(uuid.uuid4()), **dict(row)},
        )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.drop_constraint("ck_site_discovered_models_source", type_="check")
        batch.drop_column("source")
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_enabled")


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.add_column(
            sa.Column(
                "model_sync_enabled",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.add_column(
            sa.Column(
                "source",
                sa.String(length=16),
                nullable=False,
                server_default="synced",
            )
        )
        batch.create_check_constraint(
            "ck_site_discovered_models_source",
            "source IN ('manual', 'synced')",
        )
