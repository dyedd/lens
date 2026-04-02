"""add model group timeout fields

Revision ID: 20260402_0003
Revises: 20260401_0002
Create Date: 2026-04-02 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0003"
down_revision = "20260401_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(sa.Column("first_token_timeout", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("session_keep_time", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.drop_column("session_keep_time")
        batch_op.drop_column("first_token_timeout")
