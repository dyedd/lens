"""Retire the model group new-member position.

Groups append automatically joined members at the end since the editor stopped
exposing a placement choice, so the column no longer has a consumer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4f7a9e2b1d8"
down_revision: str | None = "c9f2a4b6d8e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("new_member_position")


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "new_member_position",
                sa.String(length=16),
                nullable=False,
                server_default="end",
            )
        )
