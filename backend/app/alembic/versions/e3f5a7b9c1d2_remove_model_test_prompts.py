"""移除已停用的模型测试问题设置。"""

from collections.abc import Sequence

from alembic import op

revision: str = "e3f5a7b9c1d2"
down_revision: str | None = "e3a6c9f2b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'model_test_prompts'")


def downgrade() -> None:
    # 清除的问题内容无法恢复，回退时不重建该设置。
    pass
