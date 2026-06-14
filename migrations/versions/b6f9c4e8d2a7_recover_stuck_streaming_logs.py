"""recover stuck streaming request logs

Revision ID: b6f9c4e8d2a7
Revises: 8e2f4a6c9d1b
Create Date: 2026-06-15 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b6f9c4e8d2a7"
down_revision: Union[str, Sequence[str], None] = "8e2f4a6c9d1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE request_logs
        SET lifecycle_status = 'failed',
            success = 0,
            error_message = COALESCE(
                error_message,
                'Streaming log was not finalized due to missing method in repository'
            )
        WHERE lifecycle_status = 'streaming'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE request_logs
        SET lifecycle_status = 'streaming',
            success = 0,
            error_message = NULL
        WHERE lifecycle_status = 'failed'
        AND error_message = 'Streaming log was not finalized due to missing method in repository'
        """
    )
