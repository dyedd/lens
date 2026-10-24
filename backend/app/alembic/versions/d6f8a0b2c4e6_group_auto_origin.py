"""记录模型组来源，并为自动分组增加来源过滤。

自动创建的组在最后一个成员移除后会被清理，因此需要记录来源。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6f8a0b2c4e6"
down_revision: str | None = "c3d5e7f9a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "origin",
                sa.String(length=16),
                nullable=False,
                server_default="manual",
            )
        )
        batch.add_column(
            sa.Column(
                "source_tags_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
    with op.batch_alter_table("sites") as batch:
        batch.add_column(
            sa.Column(
                "model_name_prefixes_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_name_prefixes_json")
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("source_tags_json")
        batch.drop_column("origin")
