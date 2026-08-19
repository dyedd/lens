"""remove server defaults from model prices and credential rates

Revision ID: c5e7a1d9b3f4
Revises: b9c4e8f1a2d7
Create Date: 2026-08-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5e7a1d9b3f4"
down_revision: str | None = "b9c4e8f1a2d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.alter_column("image_price_per_image", server_default=None)
    with op.batch_alter_table("site_credential_rates") as batch_op:
        batch_op.alter_column("group_name", server_default=None)
        batch_op.alter_column("last_error", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_credential_rates") as batch_op:
        batch_op.alter_column("last_error", server_default="")
        batch_op.alter_column("group_name", server_default="")
    with op.batch_alter_table("model_prices") as batch_op:
        batch_op.alter_column("image_price_per_image", server_default="0")
