"""Drop vendor-prefix aliasing from site model matching."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f9b1d2"
down_revision: str | None = "f8b0c2d4e6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_name_prefixes_json")


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        batch.add_column(
            sa.Column(
                "model_name_prefixes_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
