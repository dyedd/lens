"""protocol config auto sync

Revision ID: c3e7a1f9d4b6
Revises: b6f9c4e8d2a7
Create Date: 2026-06-19 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3e7a1f9d4b6"
down_revision: Union[str, Sequence[str], None] = "b6f9c4e8d2a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auto_sync_enabled",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.alter_column("auto_sync_enabled", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_column("auto_sync_enabled")
