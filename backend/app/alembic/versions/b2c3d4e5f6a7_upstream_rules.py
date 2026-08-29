"""convert upstream JSON objects to structured rules

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _header_rules(value: str) -> list[dict[str, Any]]:
    payload = json.loads(value or "{}")
    if not isinstance(payload, dict):
        raise ValueError("Headers must be a JSON object")
    return [
        {"name": str(name), "action": "override", "value": str(item)}
        for name, item in payload.items()
    ]


def _param_rules(value: str) -> list[dict[str, Any]]:
    payload = json.loads(value or "{}")
    if not isinstance(payload, dict):
        raise ValueError("Parameter override must be a JSON object")
    rules: list[dict[str, Any]] = []

    def visit(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for key, item in obj.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(item, dict):
                    visit(item, path)
                else:
                    rules.append({"path": path, "action": "set", "value": item})
        elif prefix:
            rules.append({"path": prefix, "action": "set", "value": obj})

    visit(payload)
    return rules


def _update_table(table: str, column: str, converter) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT id, {column} FROM {table}")).all()
    for row_id, value in rows:
        converted = converter(value)
        bind.execute(
            sa.text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
            {"id": row_id, "value": json.dumps(converted, ensure_ascii=True)},
        )


def upgrade() -> None:
    _update_table("site_protocol_configs", "headers_json", _header_rules)
    _update_table("site_protocol_configs", "param_override", _param_rules)
    _update_table("model_groups", "headers_json", _header_rules)
    _update_table("model_groups", "param_override", _param_rules)

    bind = op.get_bind()
    settings = sa.table(
        "settings", sa.column("key", sa.String()), sa.column("value", sa.Text())
    )
    rows = bind.execute(
        sa.select(settings.c.key, settings.c.value).where(
            settings.c.key.in_(
                ["upstream_headers_config", "upstream_param_override_config"]
            )
        )
    ).all()
    for key, value in rows:
        payload = json.loads(value or "{}")
        if not isinstance(payload, dict):
            raise ValueError(f"{key} must be a JSON object")
        if key == "upstream_headers_config":
            global_value = payload.get("global", {})
            if not isinstance(global_value, dict):
                raise ValueError("Global upstream headers must be an object")
            converted = _header_rules(json.dumps(global_value))
        else:
            global_value = payload.get("global", {})
            if not isinstance(global_value, dict):
                raise ValueError("Global parameter override must be an object")
            converted = _param_rules(json.dumps(global_value))
        bind.execute(
            settings.update()
            .where(settings.c.key == key)
            .values(value=json.dumps({"rules": converted}, ensure_ascii=True))
        )


def downgrade() -> None:
    bind = op.get_bind()
    _downgrade_table(bind, "site_protocol_configs", "headers_json", "headers")
    _downgrade_table(bind, "site_protocol_configs", "param_override", "params")
    _downgrade_table(bind, "model_groups", "headers_json", "headers")
    _downgrade_table(bind, "model_groups", "param_override", "params")


def _downgrade_table(bind, table: str, column: str, kind: str) -> None:
    rows = bind.execute(sa.text(f"SELECT id, {column} FROM {table}")).all()
    for row_id, value in rows:
        items = json.loads(value or "[]")
        converted: dict[str, Any] = {}
        for item in items:
            if kind == "headers":
                converted[item["name"]] = item.get("value", "")
            elif item.get("action") == "set":
                converted[item["path"]] = item.get("value")
        bind.execute(
            sa.text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),
            {"id": row_id, "value": json.dumps(converted, ensure_ascii=True)},
        )
