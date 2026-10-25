"""移除模型组的自动/手动来源标记。

模型组不再区分自动创建和手动创建，因此去掉 origin 列；
自动创建的组也不再因为成员清空而被删除。

Revision ID: f3b4c5d6e7a8
Revises: e0f1a2b3c4d5
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b4c5d6e7a8"
down_revision: str | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("origin")


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "origin",
                sa.String(length=16),
                nullable=False,
                server_default="manual",
            )
        )
