"""track manual model price overrides"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1a2b3c4d5"
down_revision: str | None = "a2c4e6f8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_prices",
        sa.Column("manual_override", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.alter_column("manual_override", server_default=None)


def downgrade() -> None:
    op.drop_column("model_prices", "manual_override")
