"""持久化规则成员及其来源、排除状态，并记录同步运行。

已保存且与组规则匹配的记录成为规则成员，拖动不再固定为手动，禁用的保持禁用。

Revision ID: d9f1b3c5e7a2
Revises: e4a6c8b0d2f1
Create Date: 2026-10-14
"""

import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "d9f1b3c5e7a2"
down_revision: str | None = "e4a6c8b0d2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _load_rule_patterns(conn: sa.Connection) -> dict[str, re.Pattern[str]]:
    patterns: dict[str, re.Pattern[str]] = {}
    for row in conn.execute(sa.text("SELECT id, pattern FROM regex_rules")).mappings():
        try:
            patterns[str(row["id"])] = re.compile(str(row["pattern"]), re.IGNORECASE)
        except re.error:
            continue
    return patterns


def _mark_rule_matched_members(conn: sa.Connection) -> None:
    patterns = _load_rule_patterns(conn)
    group_rules: dict[str, tuple[set[str], list[re.Pattern[str]]]] = {}
    for row in conn.execute(
        sa.text(
            "SELECT id, match_models_json, match_rule_ids_json FROM model_groups "
            "WHERE route_group_id = ''"
        )
    ).mappings():
        match_models = {
            str(name).casefold() for name in json.loads(row["match_models_json"])
        }
        rule_patterns = [
            patterns[rule_id]
            for rule_id in json.loads(row["match_rule_ids_json"])
            if rule_id in patterns
        ]
        if match_models or rule_patterns:
            group_rules[str(row["id"])] = (match_models, rule_patterns)

    matched_ids = []
    for row in conn.execute(
        sa.text("SELECT id, group_id, model_name FROM model_group_items")
    ).mappings():
        rules = group_rules.get(str(row["group_id"]))
        if rules is None:
            continue
        match_models, rule_patterns = rules
        model_name = str(row["model_name"])
        if model_name.casefold() in match_models or any(
            pattern.search(model_name) for pattern in rule_patterns
        ):
            matched_ids.append(row["id"])
    if matched_ids:
        conn.execute(
            sa.text("UPDATE model_group_items SET source = 'rule' WHERE id = :id"),
            [{"id": item_id} for item_id in matched_ids],
        )


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.add_column(
            sa.Column(
                "new_member_position",
                sa.String(length=16),
                nullable=False,
                server_default="end",
            )
        )
    with op.batch_alter_table("model_group_items") as batch:
        batch.add_column(
            sa.Column(
                "source", sa.String(length=16), nullable=False, server_default="manual"
            )
        )
        batch.add_column(
            sa.Column("excluded", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_check_constraint(
            "ck_model_group_items_source",
            "source IN ('manual', 'rule', 'placement')",
        )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.add_column(
            sa.Column("upstream_missing_since", sa.DateTime(), nullable=True)
        )

    conn = op.get_bind()
    _mark_rule_matched_members(conn)
    # 首次缺失从未被记录；退役时间从本次升级开始计算。
    conn.execute(
        sa.text(
            "UPDATE site_discovered_models SET upstream_missing_since = :now "
            "WHERE upstream_missing = 1"
        ),
        {"now": datetime.now(UTC).replace(tzinfo=None)},
    )

    op.create_table(
        "model_sync_runs",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_sync_runs_started_at"), "model_sync_runs", ["started_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_model_sync_runs_started_at"), table_name="model_sync_runs")
    op.drop_table("model_sync_runs")

    conn = op.get_bind()
    # 排除项本来就是禁用的记录；启用的规则成员恢复为实时匹配，
    # 禁用的则继续屏蔽匹配。
    conn.execute(
        sa.text(
            "DELETE FROM model_group_items "
            "WHERE source = 'rule' AND excluded = 0 AND enabled = 1"
        )
    )
    with op.batch_alter_table("site_discovered_models") as batch:
        batch.drop_column("upstream_missing_since")
    with op.batch_alter_table("model_group_items") as batch:
        batch.drop_constraint("ck_model_group_items_source", type_="check")
        batch.drop_column("excluded")
        batch.drop_column("source")
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_column("new_member_position")
