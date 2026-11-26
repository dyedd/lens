"""Add content-free privacy summaries to request logs."""

import sqlalchemy as sa
from alembic import op

revision = "c2f4a6b8d0e1"
down_revision = "b9f3d7a1c5e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "request_logs",
        sa.Column(
            "privacy_summary_json", sa.Text(), nullable=False, server_default="[]"
        ),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "privacy_summary_json")
