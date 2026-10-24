"""用基于名称的自动加入替换模型组匹配规则。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a9b1c3d5f7"
down_revision: str | None = "d6f8a0b2c4e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE model_group_items SET source = 'placement' WHERE source = 'rule'"
    )
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("source_tags_json")
        batch.drop_column("match_models_json")
        batch.drop_column("match_rule_ids_json")


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "source_tags_json", sa.Text(), nullable=False, server_default="[]"
            )
        )
        batch.add_column(
            sa.Column(
                "match_models_json", sa.Text(), nullable=False, server_default="[]"
            )
        )
        batch.add_column(
            sa.Column(
                "match_rule_ids_json", sa.Text(), nullable=False, server_default="[]"
            )
        )
    op.execute(
        "UPDATE model_group_items SET source = 'rule' WHERE source = 'placement'"
    )
