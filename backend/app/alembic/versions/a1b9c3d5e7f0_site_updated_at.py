"""Add sites.updated_at.

Revision ID: a1b9c3d5e7f0
Revises: e8b5c2d9a4f7
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b9c3d5e7f0"
down_revision: str | None = "e8b5c2d9a4f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "updated_at")
