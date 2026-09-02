"""Request log protocol config attribution.

Revision ID: e8b5c2d9a4f7
Revises: c8d4e6f0a1b2
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id

revision: str = "e8b5c2d9a4f7"
down_revision: str | None = "c8d4e6f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column("protocol_config_id", sa.String(length=160), nullable=True),
    )
    op.create_index(
        "ix_request_logs_protocol_config_id",
        "request_logs",
        ["protocol_config_id"],
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, channel_id FROM request_logs "
            "WHERE channel_id IS NOT NULL AND protocol_config_id IS NULL"
        )
    ).all()
    updates: dict[str, list[str]] = {}
    for log_id, channel_id in rows:
        updates.setdefault(
            protocol_config_id_from_runtime_channel_id(str(channel_id)), []
        ).append(str(log_id))
    for protocol_config_id, log_ids in updates.items():
        conn.execute(
            sa.text(
                "UPDATE request_logs SET protocol_config_id = :config_id "
                f"WHERE id IN ({', '.join(str(log_id) for log_id in log_ids)})"
            ),
            {"config_id": protocol_config_id},
        )


def downgrade() -> None:
    op.drop_index("ix_request_logs_protocol_config_id", table_name="request_logs")
    op.drop_column("request_logs", "protocol_config_id")
