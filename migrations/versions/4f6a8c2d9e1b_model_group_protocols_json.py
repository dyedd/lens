"""model group protocols json

Revision ID: 4f6a8c2d9e1b
Revises: 7c9d2e4f1a6b
Create Date: 2026-05-28 00:00:00.000000

Downgrade 只保留 protocols 列表的首项，多协议组的额外协议信息将丢失。

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4f6a8c2d9e1b"
down_revision: Union[str, Sequence[str], None] = "7c9d2e4f1a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(table_name: str, index_name: str) -> bool:
    conn = op.get_bind()
    return any(
        index["name"] == index_name
        for index in sa.inspect(conn).get_indexes(table_name)
    )


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # Step 0: 合并同名 model group 的 items 到 canonical 行（MIN(id)）
    # 旧模型按 name+protocol 区分，新模型 name 唯一。
    dup = conn.execute(sa.text(
        "SELECT name FROM model_groups GROUP BY name HAVING COUNT(*) > 1"
    )).fetchall()
    if dup:
        if dialect == "sqlite":
            op.execute("""
                UPDATE model_group_items
                SET group_id = (
                    SELECT m.cid FROM (
                        SELECT name, MIN(id) AS cid FROM model_groups GROUP BY name
                    ) m JOIN model_groups g ON g.name = m.name
                    WHERE g.id = model_group_items.group_id
                )
                WHERE group_id IN (
                    SELECT id FROM model_groups WHERE id NOT IN (
                        SELECT MIN(id) FROM model_groups GROUP BY name
                    )
                )
            """)
        elif dialect == "postgresql":
            op.execute("""
                UPDATE model_group_items AS t
                SET group_id = m.cid
                FROM model_groups g
                JOIN (SELECT name, MIN(id) AS cid FROM model_groups GROUP BY name) m
                    ON g.name = m.name
                WHERE t.group_id = g.id AND g.id <> m.cid
            """)
        else:
            raise RuntimeError(f"Unsupported dialect: {dialect}")

    # Step 1: 添加 protocols_json 列
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(
            sa.Column(
                "protocols_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    # Step 2: 聚合填充 protocols_json（按 name 聚合所有同名行的 protocol，含即将被删的行）
    if dialect == "sqlite":
        op.execute("""
            UPDATE model_groups
            SET protocols_json = COALESCE(
                (SELECT json_group_array(sub.protocol) FROM (
                    SELECT DISTINCT g2.protocol FROM model_groups g2
                    WHERE g2.name = model_groups.name
                    ORDER BY g2.protocol
                ) sub),
                '["' || protocol || '"]'
            )
        """)
    elif dialect == "postgresql":
        op.execute("""
            UPDATE model_groups AS t
            SET protocols_json = agg.protocols
            FROM (
                SELECT name, json_agg(DISTINCT protocol ORDER BY protocol)::text AS protocols
                FROM model_groups
                GROUP BY name
            ) agg
            WHERE t.name = agg.name
        """)
    else:
        raise RuntimeError(f"Unsupported dialect for upgrade: {dialect}")

    # Step 3: 删除非 canonical 行（保留每个 name 的 MIN(id)）
    if dup:
        op.execute("""
            DELETE FROM model_groups
            WHERE id NOT IN (SELECT MIN(id) FROM model_groups GROUP BY name)
        """)

    # Step 4: 删除 protocol 列 + 加 unique index
    with op.batch_alter_table("model_groups") as batch_op:
        if _index_exists("model_groups", "ix_model_groups_protocol"):
            batch_op.drop_index("ix_model_groups_protocol")
        batch_op.drop_column("protocol")

    with op.batch_alter_table("model_groups") as batch_op:
        if _index_exists("model_groups", "ix_model_groups_name"):
            batch_op.drop_index("ix_model_groups_name")
        batch_op.create_index("ix_model_groups_name", ["name"], unique=True)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(
            sa.Column(
                "protocol",
                sa.String(length=40),
                nullable=False,
                server_default="openai_chat",
            )
        )

    if dialect == "sqlite":
        op.execute("""
            UPDATE model_groups
            SET protocol = COALESCE(json_extract(protocols_json, '$[0]'), 'openai_chat')
        """)
    elif dialect == "postgresql":
        op.execute(
            "UPDATE model_groups "
            "SET protocol = COALESCE((protocols_json::jsonb -> 0) #>> '{}', 'openai_chat')"
        )
    else:
        raise RuntimeError(f"Unsupported dialect for downgrade: {dialect}")

    with op.batch_alter_table("model_groups") as batch_op:
        if _index_exists("model_groups", "ix_model_groups_name"):
            batch_op.drop_index("ix_model_groups_name")
        batch_op.create_index("ix_model_groups_name", ["name"], unique=False)
        if not _index_exists("model_groups", "ix_model_groups_protocol"):
            batch_op.create_index("ix_model_groups_protocol", ["protocol"], unique=False)

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.drop_column("protocols_json")

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.alter_column("protocol", server_default=None)
