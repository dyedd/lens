"""为模型组提供可选的、可覆盖名称匹配的正则规则。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8b0c2d4e6a8"
down_revision: str | None = "e7a9b1c3d5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "match_rule_ids_json", sa.Text(), nullable=False, server_default="[]"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("match_rule_ids_json")
