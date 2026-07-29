"""site priority

Revision ID: 7a4c9e2f1b6d
Revises: 2c7e9a1d4b6f
Create Date: 2026-07-29 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7a4c9e2f1b6d"
down_revision: Union[str, Sequence[str], None] = "2c7e9a1d4b6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.alter_column("priority", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("priority")
