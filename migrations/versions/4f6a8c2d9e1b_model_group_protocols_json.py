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
    dup = conn.execute(sa.text(
        "SELECT name, COUNT(*) AS c FROM model_groups GROUP BY name HAVING c > 1"
    )).fetchall()
    if dup:
        raise RuntimeError(
            f"Migration aborted: duplicate model group names found: {[r[0] for r in dup]}"
        )

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(
            sa.Column(
                "protocols_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    op.execute("""UPDATE model_groups SET protocols_json = '["' || protocol || '"]'""")

    with op.batch_alter_table("model_groups") as batch_op:
        if _index_exists("model_groups", "ix_model_groups_protocol"):
            batch_op.drop_index("ix_model_groups_protocol")
        batch_op.drop_column("protocol")

    with op.batch_alter_table("model_groups") as batch_op:
        if _index_exists("model_groups", "ix_model_groups_name"):
            batch_op.drop_index("ix_model_groups_name")
        batch_op.create_index("ix_model_groups_name", ["name"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.add_column(
            sa.Column(
                "protocol",
                sa.String(length=40),
                nullable=False,
                server_default="openai_chat",
            )
        )

    op.execute("""
        UPDATE model_groups
        SET protocol = COALESCE(json_extract(protocols_json, '$[0]'), 'openai_chat')
    """)

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
