"""add image token input pricing"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9a2b3c4d5e6"
down_revision: str | None = "e8f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_prices",
        sa.Column(
            "image_input_price_per_million",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.alter_column("image_input_price_per_million", server_default=None)
    op.execute(
        "UPDATE model_prices "
        "SET image_input_price_per_million = input_price_per_million"
    )


def downgrade() -> None:
    op.drop_column("model_prices", "image_input_price_per_million")
