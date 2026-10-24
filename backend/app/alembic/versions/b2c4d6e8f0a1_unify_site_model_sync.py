"""让每个已配置的站点模型都成为上游同步目标。

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
    model_rows = list(
        conn.execute(
            sa.text(
                "SELECT protocol_config_id, credential_id, protocol, model_name "
                "FROM site_discovered_models "
                # 旧的手工记录可能没有协议；它们无法被路由或
                # 同步，而 site_protocol_config_sync_targets.protocol 为 NOT NULL。
                "WHERE protocol IS NOT NULL"
            )
        ).mappings()
    )
    for row in model_rows:
        params = {"id": str(uuid.uuid4()), **dict(row)}
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM site_protocol_config_sync_targets "
                "WHERE protocol_config_id = :protocol_config_id "
                "AND credential_id = :credential_id "
                "AND protocol = :protocol "
                "AND model_name = :model_name"
            ),
            params,
        ).first()
        if exists is not None:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO site_protocol_config_sync_targets "
                "(id, protocol_config_id, credential_id, protocol, model_name) "
                "VALUES (:id, :protocol_config_id, :credential_id, :protocol, :model_name)"
            ),
            params,
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
