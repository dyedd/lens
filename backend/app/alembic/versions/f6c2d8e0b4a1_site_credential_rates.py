"""add site credential rates

Revision ID: f6c2d8e0b4a1
Revises: c0d1e2f3a4b5
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6c2d8e0b4a1"
down_revision: str | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_credential_rates",
        sa.Column("credential_id", sa.String(length=80), nullable=False),
        sa.Column("protocol_config_id", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "group_name", sa.String(length=120), nullable=False, server_default=""
        ),
        sa.Column("multiplier", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.String(length=80), nullable=True),
        sa.Column("last_synced_at", sa.String(length=80), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("credential_id"),
    )
    op.create_index(
        "ix_site_credential_rates_protocol_config_id",
        "site_credential_rates",
        ["protocol_config_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_credential_rates_protocol_config_id",
        table_name="site_credential_rates",
    )
    op.drop_table("site_credential_rates")
