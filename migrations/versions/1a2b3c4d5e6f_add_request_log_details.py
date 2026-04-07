"""add request log details

Revision ID: 1a2b3c4d5e6f
Revises: 0000
Create Date: 2026-04-07 21:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '1a2b3c4d5e6f'
down_revision = '0000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('request_logs', sa.Column('channel_name', sa.String(length=120), nullable=True))
    op.add_column('request_logs', sa.Column('is_stream', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('request_logs', sa.Column('first_token_latency_ms', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('request_logs', sa.Column('request_content', sa.Text(), nullable=True))
    op.add_column('request_logs', sa.Column('response_content', sa.Text(), nullable=True))
    op.add_column('request_logs', sa.Column('attempts_json', sa.Text(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('request_logs', 'attempts_json')
    op.drop_column('request_logs', 'response_content')
    op.drop_column('request_logs', 'request_content')
    op.drop_column('request_logs', 'first_token_latency_ms')
    op.drop_column('request_logs', 'is_stream')
    op.drop_column('request_logs', 'channel_name')
