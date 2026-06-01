"""rename supported protocols column"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6a8d0f1c2b3e"
down_revision: Union[str, Sequence[str], None] = "4f6a8c2d9e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_base_urls") as batch_op:
        batch_op.alter_column(
            "compatible_protocols_json",
            new_column_name="supported_protocols_json",
            existing_type=sa.Text(),
            existing_nullable=False,
            existing_server_default="[]",
        )


def downgrade() -> None:
    with op.batch_alter_table("site_base_urls") as batch_op:
        batch_op.alter_column(
            "supported_protocols_json",
            new_column_name="compatible_protocols_json",
            existing_type=sa.Text(),
            existing_nullable=False,
            existing_server_default="[]",
        )
