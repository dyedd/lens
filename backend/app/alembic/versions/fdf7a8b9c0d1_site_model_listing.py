"""增加渠道模型目录获取能力设置。"""

import sqlalchemy as sa
from alembic import op

revision = "fdf7a8b9c0d1"
down_revision = "fce6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "supports_model_listing", sa.Integer(), nullable=False, server_default="1"
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "supports_model_listing")
