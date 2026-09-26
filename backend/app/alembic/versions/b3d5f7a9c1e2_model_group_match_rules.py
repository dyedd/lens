"""Replace model group sync filters with match rules; repair pending credential ids.

Older admin UIs could persist credential ids as ``pending-<id>`` and later save
the same credential without the prefix, orphaning references to it.

Revision ID: b3d5f7a9c1e2
Revises: a9d3f7c1e5b2
Create Date: 2026-09-26
"""

import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5f7a9c1e2"
down_revision: str | None = "a9d3f7c1e5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PENDING_CREDENTIAL_PREFIX = "pending-"

# (table, row id column, credential id column, unique key columns)
CREDENTIAL_REFERENCES = (
    ("site_credentials", "id", "id", ("id",)),
    ("site_credential_rates", "credential_id", "credential_id", ("credential_id",)),
    (
        "site_discovered_models",
        "id",
        "credential_id",
        ("protocol_config_id", "credential_id", "protocol", "model_name"),
    ),
    (
        "model_group_items",
        "id",
        "credential_id",
        ("group_id", "channel_id", "credential_id", "model_name"),
    ),
)


def _strip_pending_credential_ids(conn: sa.Connection) -> None:
    """Rename ``pending-`` credential ids; an existing unprefixed row wins."""
    for table, row_id, column, unique_columns in CREDENTIAL_REFERENCES:
        selected = ", ".join(dict.fromkeys((row_id, *unique_columns)))
        rows = conn.execute(sa.text(f"SELECT {selected} FROM {table}")).mappings().all()
        taken_keys = {tuple(row[name] for name in unique_columns) for row in rows}
        for row in rows:
            credential_id = str(row[column])
            if not credential_id.startswith(PENDING_CREDENTIAL_PREFIX):
                continue
            stripped_id = credential_id.removeprefix(PENDING_CREDENTIAL_PREFIX)
            stripped_key = tuple(
                stripped_id if name == column else row[name] for name in unique_columns
            )
            if stripped_key in taken_keys:
                conn.execute(
                    sa.text(f"DELETE FROM {table} WHERE {row_id} = :row_id"),
                    {"row_id": row[row_id]},
                )
                continue
            taken_keys.add(stripped_key)
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET {column} = :stripped_id WHERE {row_id} = :row_id"
                ),
                {"stripped_id": stripped_id, "row_id": row[row_id]},
            )

    for row in (
        conn.execute(
            sa.text(
                "SELECT id, attempts_json FROM request_logs "
                "WHERE attempts_json LIKE :pattern"
            ),
            {"pattern": f"%{PENDING_CREDENTIAL_PREFIX}%"},
        )
        .mappings()
        .all()
    ):
        attempts = json.loads(row["attempts_json"] or "[]")
        if not isinstance(attempts, list):
            continue
        is_changed = False
        for attempt in attempts:
            credential_id = (
                attempt.get("credential_id") if isinstance(attempt, dict) else None
            )
            if isinstance(credential_id, str) and credential_id.startswith(
                PENDING_CREDENTIAL_PREFIX
            ):
                attempt["credential_id"] = credential_id.removeprefix(
                    PENDING_CREDENTIAL_PREFIX
                )
                is_changed = True
        if is_changed:
            conn.execute(
                sa.text(
                    "UPDATE request_logs SET attempts_json = :attempts WHERE id = :id"
                ),
                {"attempts": json.dumps(attempts, ensure_ascii=True), "id": row["id"]},
            )


def upgrade() -> None:
    _strip_pending_credential_ids(op.get_bind())

    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "match_models_json", sa.Text(), nullable=False, server_default="[]"
            )
        )
        batch.add_column(
            sa.Column(
                "match_regex",
                sa.Text(),
                nullable=False,
                server_default=sa.text("''"),
            )
        )

    conn = op.get_bind()
    for row in conn.execute(
        sa.text(
            "SELECT id, sync_filter_mode, sync_filter_query FROM model_groups "
            "WHERE sync_filter_mode <> '' AND route_group_id = ''"
        )
    ).mappings():
        query = str(row["sync_filter_query"] or "").strip()
        if not query:
            continue
        mode = str(row["sync_filter_mode"])
        match_models = [query] if mode == "exact" else []
        match_regex = (
            re.escape(query)
            if mode == "contains"
            else query.removeprefix("(?i)").strip()
            if mode == "regex"
            else ""
        )
        conn.execute(
            sa.text(
                "UPDATE model_groups SET match_models_json = :match_models, "
                "match_regex = :match_regex WHERE id = :id"
            ),
            {
                "match_models": json.dumps(match_models, ensure_ascii=True),
                "match_regex": match_regex,
                "id": row["id"],
            },
        )

    with op.batch_alter_table("model_groups") as batch:
        batch.drop_constraint("ck_model_groups_sync_filter_mode", type_="check")
        batch.drop_column("sync_filter_query")
        batch.drop_column("sync_filter_mode")


def downgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "sync_filter_mode",
                sa.VARCHAR(length=20),
                nullable=False,
                server_default=sa.text("''"),
            )
        )
        batch.add_column(
            sa.Column(
                "sync_filter_query",
                sa.TEXT(),
                nullable=False,
                server_default=sa.text("''"),
            )
        )
        batch.create_check_constraint(
            "ck_model_groups_sync_filter_mode",
            "sync_filter_mode IN ('', 'contains', 'exact', 'regex')",
        )

    conn = op.get_bind()
    for row in conn.execute(
        sa.text("SELECT id, match_models_json, match_regex FROM model_groups")
    ).mappings():
        match_models = json.loads(row["match_models_json"] or "[]")
        match_regex = str(row["match_regex"] or "")
        if match_regex:
            mode, query = "regex", match_regex
        elif len(match_models) == 1:
            mode, query = "exact", match_models[0]
        elif match_models:
            mode = "regex"
            query = "^(?:" + "|".join(re.escape(name) for name in match_models) + ")$"
        else:
            continue
        conn.execute(
            sa.text(
                "UPDATE model_groups SET sync_filter_mode = :mode, "
                "sync_filter_query = :query WHERE id = :id"
            ),
            {"mode": mode, "query": query, "id": row["id"]},
        )

    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("match_regex")
        batch.drop_column("match_models_json")
