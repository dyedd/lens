"""移除已废弃的站点级同步正则过滤。

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_include_rule_ids_json")
        batch.drop_column("model_sync_exclude_rule_ids_json")


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.add_column(
            sa.Column(
                "model_sync_include_rule_ids_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
        batch.add_column(
            sa.Column(
                "model_sync_exclude_rule_ids_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
