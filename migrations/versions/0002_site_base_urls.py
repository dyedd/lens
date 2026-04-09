"""site base urls

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-09
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_base_urls",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("site_id", sa.String(80), nullable=False, index=True),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, base_url FROM sites WHERE base_url IS NOT NULL AND base_url != ''")).fetchall()
    for site_id, base_url in rows:
        conn.execute(
            sa.text("INSERT INTO site_base_urls (id, site_id, url, name, enabled, sort_order) VALUES (:id, :site_id, :url, :name, 1, 0)"),
            {"id": str(uuid.uuid4()), "site_id": site_id, "url": base_url, "name": "默认"},
        )

    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("base_url")


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(sa.Column("base_url", sa.String(500), nullable=False, server_default=""))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT site_id, url FROM site_base_urls ORDER BY site_id, sort_order LIMIT 1")).fetchall()
    for site_id, url in rows:
        conn.execute(sa.text("UPDATE sites SET base_url = :url WHERE id = :site_id"), {"url": url, "site_id": site_id})

    op.drop_table("site_base_urls")
