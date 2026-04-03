"""promote site base url from protocol config to site level

Revision ID: 20260403_0010
Revises: 20260403_0009
Create Date: 2026-04-03 20:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0010"
down_revision = "20260403_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("base_url", sa.String(length=500), nullable=False, server_default=""))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT spc.site_id, MIN(spc.base_url) AS base_url
            FROM site_protocol_configs spc
            GROUP BY spc.site_id
            """
        )
    ).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE sites SET base_url = :base_url WHERE id = :site_id"),
            {"site_id": row.site_id, "base_url": row.base_url or ""},
        )

    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.drop_column("base_url")


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("base_url", sa.String(length=500), nullable=False, server_default=""))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, base_url FROM sites")).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE site_protocol_configs SET base_url = :base_url WHERE site_id = :site_id"),
            {"site_id": row.id, "base_url": row.base_url or ""},
        )

    with op.batch_alter_table("sites", recreate="always") as batch_op:
        batch_op.drop_column("base_url")
