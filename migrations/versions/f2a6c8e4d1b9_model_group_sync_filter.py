"""model group sync filter

Revision ID: f2a6c8e4d1b9
Revises: e8b7c4d9a2f1
Create Date: 2026-05-08 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6c8e4d1b9"
down_revision: Union[str, Sequence[str], None] = "e8b7c4d9a2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(
            sa.Column(
                "sync_filter_mode",
                sa.String(length=20),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "sync_filter_query",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.create_check_constraint(
            "ck_model_groups_sync_filter_mode",
            "sync_filter_mode IN ('', 'contains', 'regex')",
        )

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.alter_column("sync_filter_mode", server_default=None)
        batch_op.alter_column("sync_filter_query", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.drop_constraint("ck_model_groups_sync_filter_mode", type_="check")
        batch_op.drop_column("sync_filter_query")
        batch_op.drop_column("sync_filter_mode")
