"""require protocol base url id

Revision ID: b9d4e7a1c6f2
Revises: c9f1d3a7b8e2
Create Date: 2026-05-23 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b9d4e7a1c6f2"
down_revision: Union[str, Sequence[str], None] = "c9f1d3a7b8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("""
            SELECT id, site_id, base_url_id
            FROM site_protocol_configs
            """)
    ).mappings().all()
    for row in rows:
        base_url = bind.execute(
            sa.text("""
                SELECT id
                FROM site_base_urls
                WHERE id = :base_url_id AND site_id = :site_id
                """),
            {"base_url_id": row["base_url_id"], "site_id": row["site_id"]},
        ).scalar_one_or_none()
        if base_url:
            continue
        fallback_base_url = bind.execute(
            sa.text("""
                SELECT id
                FROM site_base_urls
                WHERE site_id = :site_id
                ORDER BY enabled DESC, sort_order ASC, id ASC
                LIMIT 1
                """),
            {"site_id": row["site_id"]},
        ).scalar_one_or_none()
        if not fallback_base_url:
            raise RuntimeError(
                f"Site protocol config {row['id']} has no available base URL"
            )
        bind.execute(
            sa.text("""
                UPDATE site_protocol_configs
                SET base_url_id = :base_url_id
                WHERE id = :id
                """),
            {"base_url_id": fallback_base_url, "id": row["id"]},
        )

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.create_check_constraint(
            "ck_site_protocol_configs_base_url_id_not_empty",
            "base_url_id <> ''",
        )


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_constraint(
            "ck_site_protocol_configs_base_url_id_not_empty",
            type_="check",
        )
