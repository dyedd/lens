"""move enablement from model groups to model group items

Revision ID: 20260402_0005
Revises: 20260402_0004
Create Date: 2026-04-02 19:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0005"
down_revision = "20260402_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.add_column(sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.drop_column("enabled")


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.drop_column("enabled")
