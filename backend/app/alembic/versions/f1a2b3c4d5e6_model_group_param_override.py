"""add model group parameter override

Revision ID: f1a2b3c4d5e6
Revises: e2a6c4f8b0d3
Create Date: 2026-08-23 00:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e2a6c4f8b0d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_groups", sa.Column("param_override", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE model_groups SET param_override = ''"))
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.alter_column("param_override", existing_type=sa.Text(), nullable=False)

    bind = op.get_bind()
    settings = sa.table(
        "settings", sa.column("key", sa.String()), sa.column("value", sa.Text())
    )
    raw_value = bind.scalar(
        sa.select(settings.c.value).where(
            settings.c.key == "upstream_param_override_config"
        )
    )
    try:
        config = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(config, dict) or "rules" not in config:
        return
    global_override = config.get("global")
    if not isinstance(global_override, dict):
        global_override = {}
    bind.execute(
        settings.update()
        .where(settings.c.key == "upstream_param_override_config")
        .values(value=json.dumps({"global": global_override}, ensure_ascii=True))
    )


def downgrade() -> None:
    op.drop_column("model_groups", "param_override")
