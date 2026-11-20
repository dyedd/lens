"""Persist model names excluded from automatic group creation."""

import sqlalchemy as sa
from alembic import op

revision = "b9f3d7a1c5e0"
down_revision = "a8e2c6f0b4d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_group_auto_create_exclusions",
        sa.Column("model_name", sa.String(200), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("model_group_auto_create_exclusions")
