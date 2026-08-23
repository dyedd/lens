"""move model request headers to model groups

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-08-23 00:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_groups", sa.Column("headers_json", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE model_groups SET headers_json = '{}'"))
    with op.batch_alter_table("model_groups") as batch_op:
        batch_op.alter_column("headers_json", existing_type=sa.Text(), nullable=False)

    bind = op.get_bind()
    settings = sa.table(
        "settings", sa.column("key", sa.String()), sa.column("value", sa.Text())
    )
    raw_value = bind.scalar(
        sa.select(settings.c.value).where(settings.c.key == "upstream_headers_config")
    )
    try:
        config = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(config, dict) or "rules" not in config:
        return
    global_headers = config.get("global")
    if not isinstance(global_headers, dict):
        global_headers = {}
    bind.execute(
        settings.update()
        .where(settings.c.key == "upstream_headers_config")
        .values(value=json.dumps({"global": global_headers}, ensure_ascii=True))
    )


def downgrade() -> None:
    op.drop_column("model_groups", "headers_json")
