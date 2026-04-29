"""request log lifecycle status

Revision ID: e8b7c4d9a2f1
Revises: c2d4e6f8a9b1
Create Date: 2026-04-29 22:30:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b7c4d9a2f1"
down_revision: Union[str, Sequence[str], None] = "c2d4e6f8a9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "lifecycle_status",
                sa.String(length=32),
                nullable=False,
                server_default="succeeded",
            )
        )
        batch_op.alter_column(
            "status_code",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.create_index(
            batch_op.f("ix_request_logs_lifecycle_status"),
            ["lifecycle_status"],
            unique=False,
        )

    op.execute(
        """
        UPDATE request_logs
        SET lifecycle_status = CASE
            WHEN success = 1 THEN 'succeeded'
            ELSE 'failed'
        END
        """
    )


def downgrade() -> None:
    op.execute("UPDATE request_logs SET status_code = 0 WHERE status_code IS NULL")
    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.drop_index(batch_op.f("ix_request_logs_lifecycle_status"))
        batch_op.alter_column(
            "status_code",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.drop_column("lifecycle_status")
