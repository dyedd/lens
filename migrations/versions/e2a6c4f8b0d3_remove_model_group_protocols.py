"""Remove derived model-group protocol storage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a6c4f8b0d3"
down_revision: str | None = "b7e9f1c3a5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("model_groups", "protocols_json")


def downgrade() -> None:
    op.add_column(
        "model_groups",
        sa.Column("protocols_json", sa.Text(), server_default="[]", nullable=False),
    )
