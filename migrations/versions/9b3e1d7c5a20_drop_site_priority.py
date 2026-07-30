"""drop site priority

Revision ID: 9b3e1d7c5a20
Revises: 7a4c9e2f1b6d
Create Date: 2026-07-30 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9b3e1d7c5a20"
down_revision: Union[str, Sequence[str], None] = "7a4c9e2f1b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("priority")


def downgrade() -> None:
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
