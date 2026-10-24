"""记录导入的每日统计的采集时间。

每个导入日记录快照时刻，此后的实时记录仍会被计入。
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "d5a8b3c1e9f7"
down_revision: str | None = "c4f7a9e2b1d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imported_stats_daily", sa.Column("imported_at", sa.DateTime(), nullable=True)
    )
    # 既有快照按当前时刻采集处理：已在库中的记录保持排除，
    # 而本次升级之后的活动仍会计入。
    op.get_bind().execute(
        sa.text("UPDATE imported_stats_daily SET imported_at = :value"),
        {"value": datetime.now(UTC).replace(tzinfo=None)},
    )
    with op.batch_alter_table("imported_stats_daily") as batch:
        batch.alter_column("imported_at", existing_type=sa.DateTime(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("imported_stats_daily") as batch:
        batch.drop_column("imported_at")
