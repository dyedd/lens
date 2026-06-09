"""gateway api key spend

Revision ID: 2b8d6f4a9c1e
Revises: 5c7a9e1d2b4f
Create Date: 2026-06-09 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2b8d6f4a9c1e"
down_revision: Union[str, Sequence[str], None] = "5c7a9e1d2b4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.add_column(
            sa.Column(
                "spent_cost_usd",
                sa.Float(),
                nullable=False,
                server_default="0",
            )
        )

    op.execute("""
        UPDATE gateway_api_keys
        SET spent_cost_usd = COALESCE((
            SELECT SUM(request_logs.total_cost_usd)
            FROM request_logs
            WHERE request_logs.gateway_key_id = gateway_api_keys.id
              AND request_logs.lifecycle_status IN ('succeeded', 'failed')
        ), 0)
    """)

    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.alter_column("spent_cost_usd", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("gateway_api_keys") as batch_op:
        batch_op.drop_column("spent_cost_usd")
