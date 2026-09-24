"""Add automatic upstream model synchronization to protocol configs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_protocol_configs",
        sa.Column("protocols_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "site_protocol_configs",
        sa.Column(
            "auto_sync_supported_models",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "site_protocol_configs",
        sa.Column(
            "auto_sync_model_pattern",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )


def downgrade() -> None:
    op.drop_column("site_protocol_configs", "auto_sync_model_pattern")
    op.drop_column("site_protocol_configs", "auto_sync_supported_models")
    op.drop_column("site_protocol_configs", "protocols_json")
