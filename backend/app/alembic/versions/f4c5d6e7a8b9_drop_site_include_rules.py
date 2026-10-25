"""移除站点的自动接入（包含）规则。

渠道同步改为把上游模型全量写入目录，不再按包含规则筛选；
排除规则仍然保留，用于阻止被删除的模型再次接入。

Revision ID: f4c5d6e7a8b9
Revises: f3b4c5d6e7a8
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c5d6e7a8b9"
down_revision: str | None = "f3b4c5d6e7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_include_rule_ids_json")


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
