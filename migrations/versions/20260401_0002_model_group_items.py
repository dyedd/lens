"""model group items schema

Revision ID: 20260401_0002
Revises: 20260401_0001
Create Date: 2026-04-01 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260401_0002"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_group_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.String(length=80), nullable=False),
        sa.Column("provider_id", sa.String(length=80), nullable=False),
        sa.Column("provider_name_snapshot", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_group_items_group_id", "model_group_items", ["group_id"], unique=False)
    op.create_index("ix_model_group_items_provider_id", "model_group_items", ["provider_id"], unique=False)

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(sa.Column("match_regex", sa.Text(), nullable=False, server_default=""))
        batch_op.drop_column("provider_ids_json")


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(sa.Column("provider_ids_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.drop_column("match_regex")

    op.drop_index("ix_model_group_items_provider_id", table_name="model_group_items")
    op.drop_index("ix_model_group_items_group_id", table_name="model_group_items")
    op.drop_table("model_group_items")
