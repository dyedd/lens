"""switch model groups to uuid ids and protocol scoped names

Revision ID: 20260402_0004
Revises: 20260402_0003
Create Date: 2026-04-02 17:10:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260402_0004"
down_revision = "20260402_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM model_groups")).fetchall()
    id_map = {row[0]: str(uuid.uuid4()) for row in rows}

    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.drop_index("ix_model_groups_name")

    for old_id, new_id in id_map.items():
        connection.execute(
            sa.text("UPDATE model_groups SET id = :new_id WHERE id = :old_id"),
            {"new_id": new_id, "old_id": old_id},
        )
        connection.execute(
            sa.text("UPDATE model_group_items SET group_id = :new_id WHERE group_id = :old_id"),
            {"new_id": new_id, "old_id": old_id},
        )

    op.create_index("ix_model_groups_name", "model_groups", ["name"], unique=False)
    op.create_index("ux_model_groups_protocol_name", "model_groups", ["protocol", "name"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.drop_index("ux_model_groups_protocol_name")
        batch_op.drop_index("ix_model_groups_name")
    op.create_index("ix_model_groups_name", "model_groups", ["name"], unique=True)
