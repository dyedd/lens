"""drop redundant site protocol proxy flag

Revision ID: 20260403_0011
Revises: 20260403_0010
Create Date: 2026-04-03 22:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0011"
down_revision = "20260403_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.drop_column("proxy")


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("proxy", sa.Integer(), nullable=False, server_default="0"))
