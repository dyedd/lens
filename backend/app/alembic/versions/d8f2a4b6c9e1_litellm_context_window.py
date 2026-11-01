"""单独保存 LiteLLM 标称上下文，避免覆盖上游上报值。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f2a4b6c9e1"
down_revision: str | None = "c7e4a1b2d3f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.add_column(
            sa.Column("litellm_context_window", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.drop_column("litellm_context_window")
