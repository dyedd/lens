"""channel proxy mode

Revision ID: 8e2f4a6c9d1b
Revises: 2b8d6f4a9c1e
Create Date: 2026-06-13 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8e2f4a6c9d1b"
down_revision: Union[str, Sequence[str], None] = "2b8d6f4a9c1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "proxy_mode",
                sa.String(length=16),
                nullable=False,
                server_default="inherit",
            )
        )

    op.execute("""
        UPDATE site_protocol_configs
        SET proxy_mode = 'custom'
        WHERE TRIM(channel_proxy) <> ''
    """)

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.alter_column("proxy_mode", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_column("proxy_mode")
