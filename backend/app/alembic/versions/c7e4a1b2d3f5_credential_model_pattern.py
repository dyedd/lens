"""渠道同步改为按凭据的模型过滤规则，并移除上游缺失标记。

每把 API Key 保存一条整名匹配的正则；同步时按它筛选上游目录，匹配不到
的模型直接删除，因此不再需要 upstream_missing 及其宽限时间。

Revision ID: c7e4a1b2d3f5
Revises: a6b7c9d1e3f0
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e4a1b2d3f5"
down_revision: str | None = "a6b7c9d1e3f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("site_credentials") as batch:
        batch.add_column(
            sa.Column(
                "model_pattern",
                sa.Text(),
                nullable=False,
                server_default=sa.text("''"),
            )
        )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.drop_column("upstream_missing_since")
        batch.drop_column("upstream_missing")


def downgrade() -> None:
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.add_column(
            sa.Column(
                "upstream_missing",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(sa.Column("upstream_missing_since", sa.DateTime(), nullable=True))
    with op.batch_alter_table("site_credentials") as batch:
        batch.drop_column("model_pattern")