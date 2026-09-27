"""Move regex patterns into a shared rule library referenced by id.

Site sync filters, model group match regexes, and the ``regex_rule_library``
setting become ``regex_rules`` rows; sites and groups keep JSON id lists.

Revision ID: c7e9a1b3d5f8
Revises: b3d5f7a9c1e2
Create Date: 2026-09-27
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e9a1b3d5f8"
down_revision: str | None = "b3d5f7a9c1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_RULE_NAME_LENGTH = 60
RULE_LIBRARY_SETTING_KEY = "regex_rule_library"


def _unique_rule_name(base_name: str, taken_names: set[str]) -> str:
    name = base_name[:MAX_RULE_NAME_LENGTH].rstrip()
    counter = 2
    while name.casefold() in taken_names:
        suffix = f" {counter}"
        name = base_name[: MAX_RULE_NAME_LENGTH - len(suffix)].rstrip() + suffix
        counter += 1
    taken_names.add(name.casefold())
    return name


def _load_library_rules(conn: sa.Connection) -> list[dict[str, str]]:
    raw_library = conn.execute(
        sa.text("SELECT value FROM settings WHERE key = :key"),
        {"key": RULE_LIBRARY_SETTING_KEY},
    ).scalar_one_or_none()
    try:
        library = json.loads(raw_library or "{}")
    except ValueError:
        return []
    rules = library.get("rules") if isinstance(library, dict) else None
    if not isinstance(rules, list):
        return []
    return [
        {
            "name": str(rule.get("name") or "").strip(),
            "pattern": str(rule.get("pattern") or ""),
            "description": str(rule.get("description") or "").strip(),
        }
        for rule in rules
        if isinstance(rule, dict)
    ]


def _move_patterns_into_rules(conn: sa.Connection) -> None:
    taken_names: set[str] = set()
    rule_ids_by_pattern: dict[str, str] = {}

    def ensure_rule_ids(raw_pattern: str, name: str, description: str = "") -> str:
        # Matching is always case-insensitive, so a leading (?i) is redundant.
        pattern = raw_pattern.strip().removeprefix("(?i)").strip()
        if not pattern:
            return "[]"
        rule_id = rule_ids_by_pattern.get(pattern)
        if rule_id is None:
            rule_id = rule_ids_by_pattern[pattern] = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO regex_rules (id, name, pattern, description) "
                    "VALUES (:id, :name, :pattern, :description)"
                ),
                {
                    "id": rule_id,
                    "name": _unique_rule_name(name or pattern, taken_names),
                    "pattern": pattern,
                    "description": description,
                },
            )
        return json.dumps([rule_id], ensure_ascii=True)

    # Library rules go first so they keep their names.
    for rule in _load_library_rules(conn):
        ensure_rule_ids(rule["pattern"], rule["name"], rule["description"])
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = :key"),
        {"key": RULE_LIBRARY_SETTING_KEY},
    )

    for row in (
        conn.execute(
            sa.text(
                "SELECT id, name, model_sync_include, model_sync_exclude FROM sites "
                "WHERE model_sync_include <> '' OR model_sync_exclude <> '' "
                "ORDER BY name"
            )
        )
        .mappings()
        .all()
    ):
        conn.execute(
            sa.text(
                "UPDATE sites SET model_sync_include_rule_ids_json = :include, "
                "model_sync_exclude_rule_ids_json = :exclude WHERE id = :id"
            ),
            {
                "include": ensure_rule_ids(
                    row["model_sync_include"], f"{row['name']} · 同步包含"
                ),
                "exclude": ensure_rule_ids(
                    row["model_sync_exclude"], f"{row['name']} · 同步排除"
                ),
                "id": row["id"],
            },
        )

    for row in (
        conn.execute(
            sa.text(
                "SELECT id, name, match_regex FROM model_groups "
                "WHERE match_regex <> '' AND route_group_id = '' ORDER BY name"
            )
        )
        .mappings()
        .all()
    ):
        conn.execute(
            sa.text(
                "UPDATE model_groups SET match_rule_ids_json = :rule_ids WHERE id = :id"
            ),
            {
                "rule_ids": ensure_rule_ids(
                    row["match_regex"], f"{row['name']} · 匹配"
                ),
                "id": row["id"],
            },
        )


def upgrade() -> None:
    op.create_table(
        "regex_rules",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column(
            "description", sa.Text(), nullable=False, server_default=sa.text("''")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regex_rules_name", "regex_rules", ["name"], unique=True)
    with op.batch_alter_table("sites") as batch:
        for column in (
            "model_sync_include_rule_ids_json",
            "model_sync_exclude_rule_ids_json",
        ):
            batch.add_column(
                sa.Column(column, sa.Text(), nullable=False, server_default="[]")
            )
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "match_rule_ids_json", sa.Text(), nullable=False, server_default="[]"
            )
        )

    _move_patterns_into_rules(op.get_bind())

    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_exclude")
        batch.drop_column("model_sync_include")
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("match_regex")


def downgrade() -> None:
    with op.batch_alter_table("sites") as batch:
        for column in ("model_sync_include", "model_sync_exclude"):
            batch.add_column(
                sa.Column(
                    column, sa.Text(), nullable=False, server_default=sa.text("''")
                )
            )
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "match_regex", sa.Text(), nullable=False, server_default=sa.text("''")
            )
        )

    conn = op.get_bind()
    patterns_by_id = {
        str(row["id"]): str(row["pattern"])
        for row in conn.execute(sa.text("SELECT id, pattern FROM regex_rules"))
        .mappings()
        .all()
    }

    def join_patterns(raw_rule_ids: str | None) -> str:
        patterns = [
            patterns_by_id[rule_id]
            for rule_id in json.loads(raw_rule_ids or "[]")
            if rule_id in patterns_by_id
        ]
        if len(patterns) == 1:
            return patterns[0]
        return "|".join(f"(?:{pattern})" for pattern in patterns)

    for row in (
        conn.execute(
            sa.text(
                "SELECT id, model_sync_include_rule_ids_json, "
                "model_sync_exclude_rule_ids_json FROM sites"
            )
        )
        .mappings()
        .all()
    ):
        conn.execute(
            sa.text(
                "UPDATE sites SET model_sync_include = :include, "
                "model_sync_exclude = :exclude WHERE id = :id"
            ),
            {
                "include": join_patterns(row["model_sync_include_rule_ids_json"]),
                "exclude": join_patterns(row["model_sync_exclude_rule_ids_json"]),
                "id": row["id"],
            },
        )
    for row in (
        conn.execute(sa.text("SELECT id, match_rule_ids_json FROM model_groups"))
        .mappings()
        .all()
    ):
        conn.execute(
            sa.text("UPDATE model_groups SET match_regex = :pattern WHERE id = :id"),
            {"pattern": join_patterns(row["match_rule_ids_json"]), "id": row["id"]},
        )

    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("match_rule_ids_json")
    with op.batch_alter_table("sites") as batch:
        batch.drop_column("model_sync_exclude_rule_ids_json")
        batch.drop_column("model_sync_include_rule_ids_json")
    op.drop_index("ix_regex_rules_name", table_name="regex_rules")
    op.drop_table("regex_rules")
