"""admin auth token version

Revision ID: 1f3a5c7e9b2d
Revises: d4f8a1c6e2b9
Create Date: 2026-07-19 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1f3a5c7e9b2d"
down_revision: Union[str, Sequence[str], None] = "d4f8a1c6e2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("admin_users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auth_token_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    with op.batch_alter_table("admin_users") as batch_op:
        batch_op.alter_column("auth_token_version", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("admin_users") as batch_op:
        batch_op.drop_column("auth_token_version")
