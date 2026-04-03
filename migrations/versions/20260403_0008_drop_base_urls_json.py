"""drop redundant base_urls_json columns

Revision ID: 20260403_0008
Revises: 20260403_0007
Create Date: 2026-04-03 18:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0008"
down_revision = "20260403_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("providers", recreate="always") as batch_op:
        batch_op.drop_column("base_urls_json")

    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.drop_column("base_urls_json")


def downgrade() -> None:
    with op.batch_alter_table("providers", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("base_urls_json", sa.Text(), nullable=False, server_default="[]"))

    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("base_urls_json", sa.Text(), nullable=False, server_default="[]"))
