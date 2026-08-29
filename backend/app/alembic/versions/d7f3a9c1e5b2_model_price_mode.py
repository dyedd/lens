"""add model price mode

Revision ID: d7f3a9c1e5b2
Revises: c5e7a1d9b3f4
Create Date: 2026-08-20 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7f3a9c1e5b2"
down_revision: str | None = "c5e7a1d9b3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_prices",
        sa.Column(
            "pricing_mode",
            sa.String(length=32),
            nullable=False,
            server_default="tokens",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE model_prices SET pricing_mode = 'non_tokens' "
            "WHERE image_price_per_image > 0 "
            "AND input_price_per_million = 0 "
            "AND output_price_per_million = 0 "
            "AND cache_read_price_per_million = 0 "
            "AND cache_write_price_per_million = 0"
        )
    )
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.alter_column("pricing_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("model_prices", "pricing_mode")
