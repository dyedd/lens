"""Remove the Auto upstream protocol.

Existing automatic-forwarding models are assigned a concrete upstream protocol:
Anthropic sites stay Anthropic, Gemini sites stay Gemini, and every other site
uses OpenAI Chat. The assignment is intentionally data-preserving: if a model
already has the target protocol row, the Auto duplicate is removed.

Revision ID: c9f2a4b6d8e0
Revises: a3c5e7f9b1d2
Create Date: 2026-10-18
"""

import json
from collections.abc import Sequence
from urllib.parse import urlparse

import sqlalchemy as sa
from alembic import op

revision: str = "c9f2a4b6d8e0"
down_revision: str | None = "a3c5e7f9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    base_urls = {
        str(row["id"]): str(row["url"] or "")
        for row in conn.execute(
            sa.text("SELECT id, url FROM site_base_urls")
        ).mappings()
    }
    targets: dict[str, str] = {}
    for row in conn.execute(
        sa.text("SELECT id, base_url_id, protocols_json FROM site_protocol_configs")
    ).mappings():
        protocols = _protocols(row["protocols_json"])
        target = _target_protocol(
            base_urls.get(str(row["base_url_id"]), ""), protocols
        )
        targets[str(row["id"])] = target
        concrete = [protocol for protocol in protocols if protocol != "auto"]
        if not concrete:
            concrete = [target]
        conn.execute(
            sa.text(
                "UPDATE site_protocol_configs SET protocols_json = :protocols "
                "WHERE id = :id"
            ),
            {"protocols": json.dumps(concrete), "id": row["id"]},
        )

    for row in conn.execute(
        sa.text(
            "SELECT id, protocol_config_id, credential_id, protocol, model_name "
            "FROM site_discovered_models "
            "WHERE protocol = 'auto' OR protocol IS NULL"
        )
    ).mappings():
        target = targets.get(str(row["protocol_config_id"]), "openai_chat")
        conflict = conn.execute(
            sa.text(
                "SELECT 1 FROM site_discovered_models "
                "WHERE protocol_config_id = :protocol_config_id "
                "AND credential_id = :credential_id "
                "AND protocol = :protocol AND model_name = :model_name "
                "AND id != :id"
            ),
            {
                "protocol_config_id": row["protocol_config_id"],
                "credential_id": row["credential_id"],
                "protocol": target,
                "model_name": row["model_name"],
                "id": row["id"],
            },
        ).first()
        if conflict is not None:
            conn.execute(
                sa.text("DELETE FROM site_discovered_models WHERE id = :id"),
                {"id": row["id"]},
            )
            continue
        conn.execute(
            sa.text(
                "UPDATE site_discovered_models SET protocol = :protocol "
                "WHERE id = :id"
            ),
            {"protocol": target, "id": row["id"]},
        )


def downgrade() -> None:
    # The previous Auto value cannot be reconstructed for every migrated model;
    # leaving the concrete assignments in place is safer than guessing.
    pass


def _protocols(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _target_protocol(base_url: str, protocols: list[str]) -> str:
    concrete = {protocol for protocol in protocols if protocol != "auto"}
    if "anthropic" in concrete and "gemini" not in concrete:
        return "anthropic"
    if "gemini" in concrete and "anthropic" not in concrete:
        return "gemini"
    host = (urlparse(base_url).hostname or "").lower()
    if "anthropic" in host or "claude" in host:
        return "anthropic"
    if "gemini" in host or "generativelanguage" in host:
        return "gemini"
    return "openai_chat"
