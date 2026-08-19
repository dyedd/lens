"""add per-image model pricing

Revision ID: b9c4e8f1a2d7
Revises: f6c2d8e0b4a1
Create Date: 2026-08-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c4e8f1a2d7"
down_revision: str | None = "f6c2d8e0b4a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_prices",
        sa.Column(
            "image_price_per_image",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("model_prices", "image_price_per_image")
