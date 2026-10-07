"""Persist the server-enforced intent for dashboard AI annotations.

Revision ID: 20260831_dashboard_ai_intent
Revises: 20260830_dashboard_latest_share
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_dashboard_ai_intent"
down_revision: Union[str, None] = "20260830_dashboard_latest_share"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_dashboard_annotation"
COLUMN = "intent"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(TABLE)}
    if COLUMN not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                COLUMN,
                sa.String(32),
                nullable=False,
                server_default="modify",
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(TABLE)}
    if COLUMN in columns:
        op.drop_column(TABLE, COLUMN)
