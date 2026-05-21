"""gateway api key user agent

Revision ID: a7c5e9d1f3b2
Revises: f2a6c8e4d1b9
Create Date: 2026-05-20 18:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7c5e9d1f3b2"
down_revision: Union[str, Sequence[str], None] = "f2a6c8e4d1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.add_column(
            sa.Column(
                "client_user_agent",
                sa.String(length=300),
                nullable=False,
                server_default="",
            )
        )

    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.alter_column("client_user_agent", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.drop_column("client_user_agent")
