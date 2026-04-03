"""normalize stored provider base urls to root endpoints

Revision ID: 20260403_0009
Revises: 20260403_0008
Create Date: 2026-04-03 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0009"
down_revision = "20260403_0008"
branch_labels = None
depends_on = None


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    if normalized.endswith("/v1beta"):
        return normalized[:-7]
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


def upgrade() -> None:
    connection = op.get_bind()

    providers = connection.execute(sa.text("SELECT id, base_url FROM providers")).fetchall()
    for row in providers:
        normalized = _normalize(row.base_url)
        if normalized != row.base_url:
            connection.execute(
                sa.text("UPDATE providers SET base_url = :base_url WHERE id = :id"),
                {"id": row.id, "base_url": normalized},
            )

    protocols = connection.execute(sa.text("SELECT id, base_url FROM site_protocol_configs")).fetchall()
    for row in protocols:
        normalized = _normalize(row.base_url)
        if normalized != row.base_url:
            connection.execute(
                sa.text("UPDATE site_protocol_configs SET base_url = :base_url WHERE id = :id"),
                {"id": row.id, "base_url": normalized},
            )


def downgrade() -> None:
    pass
