"""drop redundant site protocol label

Revision ID: 20260403_0007
Revises: 20260402_0006
Create Date: 2026-04-03 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0007"
down_revision = "20260402_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.drop_column("label")


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("label", sa.String(length=120), nullable=False, server_default=""))

