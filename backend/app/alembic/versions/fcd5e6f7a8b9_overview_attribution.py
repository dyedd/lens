"""保存模型和渠道的历史用量。"""

import sqlalchemy as sa
from alembic import op

revision = "fcd5e6f7a8b9"
down_revision = "c7e4a1b2d3f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column(
            "attribution_archived", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    with op.batch_alter_table("request_logs") as batch:
        batch.alter_column("attribution_archived", server_default=None)
    op.create_table(
        "overview_attribution_hourly_stats",
        sa.Column("hour_start", sa.DateTime(), primary_key=True),
        sa.Column("upstream_model", sa.String(200), primary_key=True),
        sa.Column("channel_id", sa.String(160), primary_key=True),
        sa.Column("channel_name", sa.String(120), nullable=False),
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
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
        ],
        *[
            sa.Column(name, sa.Float(), nullable=False)
            for name in (
                "input_cost_usd",
                "output_cost_usd",
                "total_cost_usd",
            )
        ],
    )
    for dimension in ("channel", "model"):
        op.create_index(
            f"ix_overview_attribution_hourly_stats_{dimension}_hour",
            "overview_attribution_hourly_stats",
            [
                "channel_id" if dimension == "channel" else "upstream_model",
                "hour_start",
            ],
        )


def downgrade() -> None:
    op.drop_table("overview_attribution_hourly_stats")
    with op.batch_alter_table("request_logs") as batch:
        batch.drop_column("attribution_archived")
