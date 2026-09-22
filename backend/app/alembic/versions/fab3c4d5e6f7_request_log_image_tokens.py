"""add image input token accounting"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fab3c4d5e6f7"
down_revision: str | None = "f9a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column(
            "image_input_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.alter_column("image_input_tokens", server_default=None)


def downgrade() -> None:
    op.drop_column("request_logs", "image_input_tokens")
