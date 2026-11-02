"""按 Agent 保存模型和渠道归因。"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "fcd5e6f7a8b9"
branch_labels = None
depends_on = None

TABLE = "overview_attribution_hourly_stats"
NEW_TABLE = f"{TABLE}_with_agent"
INDEXES = {
    "channel": ("channel_id", "hour_start"),
    "model": ("upstream_model", "hour_start"),
    "agent": ("agent", "hour_start"),
}
INTEGER_COLUMNS = (
    "request_count",
    "successful_requests",
    "failed_requests",
    "wait_time_ms",
    "input_tokens",
    "cache_read_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "total_tokens",
)
FLOAT_COLUMNS = ("input_cost_usd", "output_cost_usd", "total_cost_usd")
ALL_COLUMNS = (
    "hour_start",
    "upstream_model",
    "channel_id",
    "agent",
    "channel_name",
    *INTEGER_COLUMNS,
    *FLOAT_COLUMNS,
)


def _classify_user_agent(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "unknown"
    if "codex" in normalized:
        return "codex"
    if "claude" in normalized:
        return "claude_code"
    return "other"


def _utc_naive(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _backfill_agents() -> None:
    bind = op.get_bind()
    archived_rows = {
        (
            _utc_naive(row["hour_start"]),
            row["upstream_model"],
            row["channel_id"],
            row["agent"],
        ): dict(row)
        for row in bind.execute(
            sa.text(f"SELECT {', '.join(ALL_COLUMNS)} FROM {TABLE}")
        ).mappings()
    }
    request_columns = (
        "created_at",
        "lifecycle_status",
        "upstream_model_name",
        "channel_id",
        "channel_name",
        "user_agent",
        "latency_ms",
        *INTEGER_COLUMNS[4:],
        *FLOAT_COLUMNS,
    )
    requests = bind.execute(
        sa.text(
            f"SELECT {', '.join(request_columns)} FROM request_logs "
            "WHERE attribution_archived = 1 "
            "AND lifecycle_status IN ('succeeded', 'failed', 'cancelled')"
        )
    ).mappings()
    for request in requests:
        agent = _classify_user_agent(request["user_agent"])
        if agent == "unknown":
            continue
        created_at = _utc_naive(request["created_at"])
        hour_start = created_at.replace(
            minute=created_at.minute // 15 * 15,
            second=0,
            microsecond=0,
        )
        model = str(request["upstream_model_name"] or "")[:200]
        channel_id = str(request["channel_id"] or "")[:160]
        unknown_key = (hour_start, model, channel_id, "unknown")
        source = archived_rows.get(unknown_key)
        if source is None or int(source["request_count"]) < 1:
            continue
        contribution = {
            "request_count": 1,
            "successful_requests": int(request["lifecycle_status"] == "succeeded"),
            "failed_requests": int(request["lifecycle_status"] == "failed"),
            "wait_time_ms": int(request["latency_ms"] or 0),
            **{name: int(request[name] or 0) for name in INTEGER_COLUMNS[4:]},
            **{name: float(request[name] or 0) for name in FLOAT_COLUMNS},
        }
        if any(
            float(source[name]) < float(value) for name, value in contribution.items()
        ):
            continue
        target_key = (hour_start, model, channel_id, agent)
        target = archived_rows.setdefault(
            target_key,
            {
                **source,
                "agent": agent,
                "channel_name": str(request["channel_name"] or ""),
                **dict.fromkeys(INTEGER_COLUMNS, 0),
                **dict.fromkeys(FLOAT_COLUMNS, 0.0),
            },
        )
        for name, value in contribution.items():
            source[name] -= value
            target[name] += value
        if request["channel_name"]:
            target["channel_name"] = str(request["channel_name"])

    archived_rows = {
        key: row for key, row in archived_rows.items() if row["request_count"] > 0
    }
    bind.execute(sa.text(f"DELETE FROM {TABLE}"))
    if archived_rows:
        parameters = ", ".join(f":{name}" for name in ALL_COLUMNS)
        bind.execute(
            sa.text(
                f"INSERT INTO {TABLE} ({', '.join(ALL_COLUMNS)}) VALUES ({parameters})"
            ),
            list(archived_rows.values()),
        )


def _create_table(name: str, *, include_agent: bool) -> None:
    columns = [
        sa.Column("hour_start", sa.DateTime(), nullable=False),
        sa.Column("upstream_model", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(160), nullable=False),
    ]
    if include_agent:
        columns.append(sa.Column("agent", sa.String(32), nullable=False))
    columns.extend(
        [
            sa.Column("channel_name", sa.String(120), nullable=False),
            *[
                sa.Column(name, sa.Integer(), nullable=False)
                for name in INTEGER_COLUMNS
            ],
            *[sa.Column(name, sa.Float(), nullable=False) for name in FLOAT_COLUMNS],
        ]
    )
    primary_key = ["hour_start", "upstream_model", "channel_id"]
    if include_agent:
        primary_key.append("agent")
    columns.append(sa.PrimaryKeyConstraint(*primary_key))
    op.create_table(name, *columns)


def _create_indexes(*, include_agent: bool) -> None:
    dimensions = (
        ("channel", "model", "agent") if include_agent else ("channel", "model")
    )
    for dimension in dimensions:
        columns = INDEXES[dimension]
        op.create_index(
            f"ix_{TABLE}_{dimension}_hour",
            TABLE,
            list(columns),
        )


def _drop_indexes(*, include_agent: bool) -> None:
    dimensions = (
        ("channel", "model", "agent") if include_agent else ("channel", "model")
    )
    for dimension in dimensions:
        op.drop_index(f"ix_{TABLE}_{dimension}_hour", table_name=TABLE)


def upgrade() -> None:
    _create_table(NEW_TABLE, include_agent=True)
    columns = [
        "hour_start",
        "upstream_model",
        "channel_id",
        "agent",
        "channel_name",
        *INTEGER_COLUMNS,
        *FLOAT_COLUMNS,
    ]
    old_columns = [
        "hour_start",
        "upstream_model",
        "channel_id",
        "channel_name",
        *INTEGER_COLUMNS,
        *FLOAT_COLUMNS,
    ]
    op.execute(
        sa.text(
            f"INSERT INTO {NEW_TABLE} ({', '.join(columns)}) "
            f"SELECT hour_start, upstream_model, channel_id, 'unknown', "
            f"{', '.join(old_columns[3:])} FROM {TABLE}"
        )
    )
    _drop_indexes(include_agent=False)
    op.drop_table(TABLE)
    op.rename_table(NEW_TABLE, TABLE)
    _backfill_agents()
    _create_indexes(include_agent=True)


def downgrade() -> None:
    old_table = f"{TABLE}_without_agent"
    _create_table(old_table, include_agent=False)
    columns = [
        "hour_start",
        "upstream_model",
        "channel_id",
        "channel_name",
        *INTEGER_COLUMNS,
        *FLOAT_COLUMNS,
    ]
    aggregates = [
        "hour_start",
        "upstream_model",
        "channel_id",
        "MAX(channel_name)",
        *[f"SUM({name})" for name in INTEGER_COLUMNS],
        *[f"SUM({name})" for name in FLOAT_COLUMNS],
    ]
    op.execute(
        sa.text(
            f"INSERT INTO {old_table} ({', '.join(columns)}) "
            f"SELECT {', '.join(aggregates)} FROM {TABLE} "
            "GROUP BY hour_start, upstream_model, channel_id"
        )
    )
    _drop_indexes(include_agent=True)
    op.drop_table(TABLE)
    op.rename_table(old_table, TABLE)
    _create_indexes(include_agent=False)
