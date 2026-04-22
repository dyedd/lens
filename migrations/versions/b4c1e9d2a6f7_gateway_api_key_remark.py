"""gateway api key remark

Revision ID: b4c1e9d2a6f7
Revises: 9a7d4f2c8e31
Create Date: 2026-04-21 23:05:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c1e9d2a6f7"
down_revision: Union[str, Sequence[str], None] = "9a7d4f2c8e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.alter_column("name", new_column_name="remark")

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE gateway_api_keys
            SET remark = ''
            WHERE remark IN ('API key', 'Default key')
               OR remark LIKE 'Imported key %'
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.alter_column("remark", new_column_name="name")
