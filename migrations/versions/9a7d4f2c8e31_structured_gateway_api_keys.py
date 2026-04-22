"""structured gateway api keys

Revision ID: 9a7d4f2c8e31
Revises: ffb1f20c2bd8
Create Date: 2026-04-21 22:10:00.000000

"""
from __future__ import annotations

from datetime import datetime
import secrets
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a7d4f2c8e31"
down_revision: Union[str, Sequence[str], None] = "ffb1f20c2bd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


KEY_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
LEGACY_GATEWAY_API_KEYS = "gateway_api_keys"
LEGACY_GATEWAY_API_KEY_HINT = "gateway_api_key_hint"
LEGACY_GATEWAY_REQUIRE_API_KEY = "gateway_require_api_key"
LEGACY_TEST_GATEWAY_KEY = "test-gateway-key"


def upgrade() -> None:
    op.create_table(
        "gateway_api_keys",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("allowed_models_json", sa.Text(), nullable=False),
        sa.Column("max_cost_usd", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key"),
    )
    bind = op.get_bind()
    legacy_keys = _load_legacy_gateway_keys(bind)
    seed_keys = legacy_keys or [_generate_gateway_api_key()]
    now = datetime.utcnow()
    rows = []
    legacy_key_id_map: dict[str, str] = {}
    seen: set[str] = set()
    for index, secret in enumerate(seed_keys, start=1):
        api_key = _generate_gateway_api_key() if secret == LEGACY_TEST_GATEWAY_KEY else secret
        if api_key in seen:
            continue
        seen.add(api_key)
        key_id = uuid.uuid4().hex
        rows.append(
            {
                "id": key_id,
                "name": "Default key" if index == 1 else f"Imported key {index}",
                "api_key": api_key,
                "enabled": 1,
                "allowed_models_json": "[]",
                "max_cost_usd": 0.0,
                "expires_at": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        legacy_key_id_map[secret] = key_id

    if rows:
        gateway_api_keys = sa.table(
            "gateway_api_keys",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("api_key", sa.Text),
            sa.column("enabled", sa.Integer),
            sa.column("allowed_models_json", sa.Text),
            sa.column("max_cost_usd", sa.Float),
            sa.column("expires_at", sa.DateTime),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        )
        bind.execute(gateway_api_keys.insert(), rows)
        for legacy_secret, key_id in legacy_key_id_map.items():
            bind.execute(
                sa.text(
                    "UPDATE request_logs SET gateway_key_id = :key_id WHERE gateway_key_id = :legacy_secret"
                ),
                {"key_id": key_id, "legacy_secret": legacy_secret},
            )

    bind.execute(
        sa.text(
            "DELETE FROM settings WHERE key IN (:keys, :hint, :require_key)"
        ),
        {
            "keys": LEGACY_GATEWAY_API_KEYS,
            "hint": LEGACY_GATEWAY_API_KEY_HINT,
            "require_key": LEGACY_GATEWAY_REQUIRE_API_KEY,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, api_key FROM gateway_api_keys ORDER BY created_at ASC, id ASC")
    ).fetchall()
    keys_value = "\n".join(str(row[1]).strip() for row in rows if str(row[1]).strip())
    for row in rows:
        key_id = str(row[0]).strip()
        api_key = str(row[1]).strip()
        if not key_id or not api_key:
            continue
        bind.execute(
            sa.text(
                "UPDATE request_logs SET gateway_key_id = :api_key WHERE gateway_key_id = :key_id"
            ),
            {"api_key": api_key, "key_id": key_id},
        )
    bind.execute(
        sa.text("DELETE FROM settings WHERE key IN (:keys, :hint)"),
        {"keys": LEGACY_GATEWAY_API_KEYS, "hint": LEGACY_GATEWAY_API_KEY_HINT},
    )
    bind.execute(
        sa.text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
        {"key": LEGACY_GATEWAY_API_KEYS, "value": keys_value},
    )
    bind.execute(
        sa.text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
        {"key": LEGACY_GATEWAY_API_KEY_HINT, "value": ""},
    )
    op.drop_table("gateway_api_keys")


def _load_legacy_gateway_keys(bind) -> list[str]:
    try:
        row = bind.execute(
            sa.text("SELECT value FROM settings WHERE key = :key"),
            {"key": LEGACY_GATEWAY_API_KEYS},
        ).fetchone()
    except Exception:
        return []
    if row is None:
        return []

    raw_value = str(row[0] or "")
    keys: list[str] = []
    seen: set[str] = set()
    for item in raw_value.replace("\r", "\n").split("\n"):
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        keys.append(normalized)
    return keys


def _generate_gateway_api_key() -> str:
    return "sk-lens-" + "".join(secrets.choice(KEY_CHARS) for _ in range(48))
