"""为协议专用地址和国内地址增加端点类型。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0f1a2b3c4d5"
down_revision: str | None = "d5a8b3c1e9f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_base_urls",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="default",
        ),
    )
    with op.batch_alter_table("site_base_urls") as batch:
        batch.alter_column("kind", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("site_base_urls") as batch:
        batch.drop_column("kind")
