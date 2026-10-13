"""Add input-context price tiers to model prices.

Revision ID: d2f4a6c8e0b1
Revises: c7e9a1b3d5f8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2f4a6c8e0b1"
down_revision: str | None = "c7e9a1b3d5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.add_column(sa.Column("context_tiers_json", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE model_prices SET context_tiers_json = '[]'"))
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.alter_column(
            "context_tiers_json", existing_type=sa.Text(), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.drop_column("context_tiers_json")
