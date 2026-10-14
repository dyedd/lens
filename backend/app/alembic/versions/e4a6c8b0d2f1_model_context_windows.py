"""Add context windows to channel models and model groups.

Revision ID: e4a6c8b0d2f1
Revises: c7e9a1b3d5f8
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a6c8b0d2f1"
down_revision: str | None = "c7e9a1b3d5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.add_column(sa.Column("context_window", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("upstream_context_window", sa.Integer(), nullable=True)
        )
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(sa.Column("context_window", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("context_window")
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.drop_column("upstream_context_window")
        batch.drop_column("context_window")
