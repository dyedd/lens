"""Move multimodal fallback mappings onto model groups.

Revision ID: c8d4e6f0a1b2
Revises: b2c3d4e5f6a7
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4e6f0a1b2"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_groups",
        sa.Column("fallback_group_ids_json", sa.Text(), nullable=True),
    )
    op.execute(sa.text("UPDATE model_groups SET fallback_group_ids_json = '[]'"))
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.alter_column(
            "fallback_group_ids_json", existing_type=sa.Text(), nullable=False
        )

    bind = op.get_bind()
    groups = sa.table(
        "model_groups",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("fallback_group_ids_json", sa.Text()),
    )
    settings = sa.table(
        "settings", sa.column("key", sa.String()), sa.column("value", sa.Text())
    )
    raw_value = bind.scalar(
        sa.select(settings.c.value).where(settings.c.key == "multimodal_fallback")
    )
    if raw_value is None or not str(raw_value).strip():
        bind.execute(sa.delete(settings).where(settings.c.key == "multimodal_fallback"))
        return
    try:
        mapping = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Cannot migrate invalid multimodal fallback setting"
        ) from exc
    if not isinstance(mapping, dict):
        raise RuntimeError(
            "Cannot migrate multimodal fallback setting: expected object"
        )

    rows = bind.execute(sa.select(groups.c.id, groups.c.name)).all()
    groups_by_name = {str(name): str(group_id) for group_id, name in rows}
    for source_name, target_name in mapping.items():
        if not isinstance(source_name, str) or not isinstance(target_name, str):
            raise RuntimeError(
                "Cannot migrate multimodal fallback: names must be strings"
            )
        source_id = groups_by_name.get(source_name.strip())
        target_id = groups_by_name.get(target_name.strip())
        if source_id is None or target_id is None:
            missing = source_name if source_id is None else target_name
            raise RuntimeError(
                f"Cannot migrate multimodal fallback: model group not found: {missing}"
            )
        if source_id == target_id:
            raise RuntimeError(
                "Cannot migrate multimodal fallback: group cannot fall back to itself"
            )
        bind.execute(
            groups.update()
            .where(groups.c.id == source_id)
            .values(fallback_group_ids_json=json.dumps([target_id]))
        )

    bind.execute(sa.delete(settings).where(settings.c.key == "multimodal_fallback"))


def downgrade() -> None:
    op.add_column(
        "settings", sa.Column("multimodal_fallback", sa.Text(), nullable=True)
    )
    op.drop_column("model_groups", "fallback_group_ids_json")
