"""把模型组正则改为组内保存，并保留旧规则引用兼容升级。"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c9d1e3f0"
down_revision: str | None = "f4c5d6e7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "match_regex", sa.Text(), nullable=False, server_default=sa.text("''")
            )
        )
        batch.add_column(
            sa.Column(
                "match_regex_operator",
                sa.String(length=8),
                nullable=False,
                server_default="or",
            )
        )

    conn = op.get_bind()
    patterns = {
        str(row["id"]): str(row["pattern"])
        for row in conn.execute(sa.text("SELECT id, pattern FROM regex_rules"))
        .mappings()
        .all()
    }
    for row in conn.execute(
        sa.text("SELECT id, match_rule_ids_json FROM model_groups")
    ).mappings():
        rule_patterns = [
            patterns[rule_id]
            for rule_id in json.loads(row["match_rule_ids_json"] or "[]")
            if rule_id in patterns and patterns[rule_id]
        ]
        if not rule_patterns:
            continue
        regex = (
            rule_patterns[0]
            if len(rule_patterns) == 1
            else "(?:" + ")|(?:".join(rule_patterns) + ")"
        )
        conn.execute(
            sa.text(
                "UPDATE model_groups SET match_regex = :regex, "
                "match_regex_operator = 'or' WHERE id = :id"
            ),
            {"regex": regex, "id": row["id"]},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for row in conn.execute(
        sa.text(
            "SELECT id, match_regex, match_rule_ids_json "
            "FROM model_groups WHERE match_regex <> ''"
        )
    ).mappings():
        rule_ids = json.loads(row["match_rule_ids_json"] or "[]")
        if rule_ids:
            continue
        rule_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO regex_rules (id, name, pattern, description) "
                "VALUES (:id, :name, :pattern, '')"
            ),
            {
                "id": rule_id,
                "name": f"migrated-{row['id']}"[:60],
                "pattern": row["match_regex"],
            },
        )
        conn.execute(
            sa.text(
                "UPDATE model_groups SET match_rule_ids_json = :rule_ids WHERE id = :id"
            ),
            {"rule_ids": json.dumps([rule_id]), "id": row["id"]},
        )
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("match_regex_operator")
        batch.drop_column("match_regex")
