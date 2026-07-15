"""model group item uniqueness

Revision ID: d4f8a1c6e2b9
Revises: c3e7a1f9d4b6
Create Date: 2026-07-15 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4f8a1c6e2b9"
down_revision: Union[str, Sequence[str], None] = "c3e7a1f9d4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _merge_duplicate_group_items() -> None:
    connection = op.get_bind()
    items = sa.table(
        "model_group_items",
        sa.column("id", sa.Integer()),
        sa.column("group_id", sa.String()),
        sa.column("channel_id", sa.String()),
        sa.column("credential_id", sa.String()),
        sa.column("model_name", sa.String()),
        sa.column("enabled", sa.Integer()),
        sa.column("sort_order", sa.Integer()),
    )
    duplicate_keys = (
        connection.execute(
            sa.select(
                items.c.group_id,
                items.c.channel_id,
                items.c.credential_id,
                items.c.model_name,
                sa.func.max(items.c.enabled).label("enabled"),
            )
            .group_by(
                items.c.group_id,
                items.c.channel_id,
                items.c.credential_id,
                items.c.model_name,
            )
            .having(sa.func.count(items.c.id) > 1)
        )
        .mappings()
        .all()
    )

    for duplicate in duplicate_keys:
        duplicate_ids = list(
            connection.execute(
                sa.select(items.c.id)
                .where(items.c.group_id == duplicate["group_id"])
                .where(items.c.channel_id == duplicate["channel_id"])
                .where(items.c.credential_id == duplicate["credential_id"])
                .where(items.c.model_name == duplicate["model_name"])
                .order_by(items.c.sort_order.asc(), items.c.id.asc())
            ).scalars()
        )
        keep_id, *remove_ids = duplicate_ids
        connection.execute(
            sa.update(items)
            .where(items.c.id == keep_id)
            .values(enabled=int(duplicate["enabled"]))
        )
        connection.execute(sa.delete(items).where(items.c.id.in_(remove_ids)))


def upgrade() -> None:
    _merge_duplicate_group_items()
    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.create_unique_constraint(
            "uq_model_group_items_target",
            ["group_id", "channel_id", "credential_id", "model_name"],
        )


def downgrade() -> None:
    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.drop_constraint(
            "uq_model_group_items_target",
            type_="unique",
        )
