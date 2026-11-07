"""修复旧共享规则迁移后嵌套的正则全局标记。"""

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.model_group_matching import combine_model_group_patterns

revision: str = "d2f4a6b8c0e1"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    rules = dict(
        connection.execute(sa.text("SELECT id, pattern FROM regex_rules")).all()
    )
    groups = connection.execute(
        sa.text("SELECT id, match_regex, match_rule_ids_json FROM model_groups")
    ).mappings()
    for group in groups:
        try:
            re.compile(group["match_regex"])
        except re.error:
            pass
        else:
            continue
        patterns = [
            rules[rule_id]
            for rule_id in json.loads(group["match_rule_ids_json"] or "[]")
            if rule_id in rules and rules[rule_id]
        ]
        # 只重建仍与旧迁移结果相同的表达式，保留之后的手工编辑。
        if (
            len(patterns) < 2
            or group["match_regex"] != "(?:" + ")|(?:".join(patterns) + ")"
        ):
            continue
        combined = combine_model_group_patterns(patterns)
        connection.execute(
            sa.text("UPDATE model_groups SET match_regex = :pattern WHERE id = :id"),
            {"pattern": combined, "id": group["id"]},
        )


def downgrade() -> None:
    # 修复后的表达式也适用于旧版本，无需恢复非法表达式。
    pass
