"""site protocol combo name

Revision ID: 7c9d2e4f1a6b
Revises: 3e9a1f7c
Create Date: 2026-05-28 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7c9d2e4f1a6b"
down_revision: Union[str, Sequence[str], None] = "3e9a1f7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "name",
                sa.String(length=120),
                nullable=False,
                server_default="",
            )
        )

    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.alter_column("name", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_column("name")
