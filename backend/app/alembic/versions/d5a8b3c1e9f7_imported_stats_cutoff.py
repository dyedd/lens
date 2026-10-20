"""Record when imported daily stats were captured.

Imported stats used to shadow a whole local day, so requests made after the
import on that same day disappeared from the overview. Each imported day now
carries the instant of its snapshot, which lets live rows after it still count.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "d5a8b3c1e9f7"
down_revision: str | None = "c4f7a9e2b1d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "imported_stats_daily", sa.Column("imported_at", sa.DateTime(), nullable=True)
    )
    # Existing snapshots are treated as captured now: rows already in the
    # database stay excluded, while activity after this upgrade counts.
    op.get_bind().execute(
        sa.text("UPDATE imported_stats_daily SET imported_at = :value"),
        {"value": datetime.now(UTC).replace(tzinfo=None)},
    )
    with op.batch_alter_table("imported_stats_daily") as batch:
        batch.alter_column("imported_at", existing_type=sa.DateTime(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("imported_stats_daily") as batch:
        batch.drop_column("imported_at")
