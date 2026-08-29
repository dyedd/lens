"""add request log billing units

Revision ID: a4c8e2f6b1d9
Revises: d7f3a9c1e5b2
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e2f6b1d9"
down_revision: str | None = "d7f3a9c1e5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column(
            "billing_mode",
            sa.String(length=32),
            nullable=False,
            server_default="tokens",
        ),
    )
    op.add_column(
        "request_logs",
        sa.Column(
            "billing_units",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.alter_column("billing_mode", server_default=None)
        batch_op.alter_column("billing_units", server_default=None)


def downgrade() -> None:
    op.drop_column("request_logs", "billing_units")
    op.drop_column("request_logs", "billing_mode")
