"""store the request rate multiplier snapshot

Revision ID: b7e9f1c3a5d2
Revises: a4c8e2f6b1d9
Create Date: 2026-08-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e9f1c3a5d2"
down_revision: str | None = "a4c8e2f6b1d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("rate_multiplier", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "rate_multiplier")
