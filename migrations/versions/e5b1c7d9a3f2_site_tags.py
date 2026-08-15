"""add site tags

Revision ID: e5b1c7d9a3f2
Revises: d9e0f1a2b3c4
Create Date: 2026-08-14 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b1c7d9a3f2"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(
            sa.Column(
                "tags_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("tags_json")
