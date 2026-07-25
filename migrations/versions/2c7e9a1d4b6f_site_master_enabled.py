"""site master enabled

Revision ID: 2c7e9a1d4b6f
Revises: 1f3a5c7e9b2d
Create Date: 2026-07-26 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2c7e9a1d4b6f"
down_revision: Union[str, Sequence[str], None] = "1f3a5c7e9b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(
            sa.Column(
                "enabled",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )

    op.execute("""
        UPDATE sites
        SET enabled = 0
        WHERE NOT EXISTS (
            SELECT 1
            FROM site_protocol_configs
            WHERE site_protocol_configs.site_id = sites.id
              AND site_protocol_configs.enabled = 1
        )
        """)
    op.execute("""
        UPDATE site_protocol_configs
        SET enabled = 1
        WHERE site_id IN (SELECT id FROM sites WHERE enabled = 0)
        """)

    with op.batch_alter_table("sites") as batch_op:
        batch_op.alter_column("enabled", server_default=None)


def downgrade() -> None:
    op.execute("""
        UPDATE site_protocol_configs
        SET enabled = 0
        WHERE site_id IN (SELECT id FROM sites WHERE enabled = 0)
        """)
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("enabled")
