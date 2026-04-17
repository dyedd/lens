"""remove model group match regex

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = {col["name"] for col in sa.inspect(conn).get_columns("model_groups")}
    if "match_regex" in columns:
        with op.batch_alter_table("model_groups") as batch_op:
            batch_op.drop_column("match_regex")


def downgrade() -> None:
    conn = op.get_bind()
    columns = {col["name"] for col in sa.inspect(conn).get_columns("model_groups")}
    if "match_regex" not in columns:
        op.add_column(
            "model_groups",
            sa.Column("match_regex", sa.Text(), nullable=False, server_default=""),
        )
