"""combo protocols json

Revision ID: 5c7a9e1d2b4f
Revises: 6a8d0f1c2b3e
Create Date: 2026-06-04 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5c7a9e1d2b4f"
down_revision: Union[str, Sequence[str], None] = "6a8d0f1c2b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "protocols_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("""
            UPDATE site_protocol_configs
            SET protocols_json = COALESCE(
                NULLIF((
                    SELECT b.supported_protocols_json
                    FROM site_base_urls b
                    WHERE b.id = site_protocol_configs.base_url_id
                ), '[]'),
                (SELECT json_group_array(protocol) FROM (
                    SELECT DISTINCT m.protocol
                    FROM site_discovered_models m
                    WHERE m.protocol_config_id = site_protocol_configs.id
                      AND m.protocol IS NOT NULL
                    ORDER BY m.protocol
                )),
                '[]'
            )
        """)
    elif dialect == "postgresql":
        op.execute("""
            UPDATE site_protocol_configs AS p
            SET protocols_json = COALESCE(
                NULLIF(b.supported_protocols_json, '[]'),
                (
                    SELECT json_agg(DISTINCT m.protocol ORDER BY m.protocol)::text
                    FROM site_discovered_models m
                    WHERE m.protocol_config_id = p.id
                      AND m.protocol IS NOT NULL
                ),
                '[]'
            )
            FROM site_base_urls b
            WHERE b.id = p.base_url_id
        """)
    else:
        raise RuntimeError(f"Unsupported dialect for migration 5c7a9e1d2b4f: {dialect}")


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_column("protocols_json")
