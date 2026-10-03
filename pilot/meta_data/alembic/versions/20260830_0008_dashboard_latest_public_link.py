"""Add one stable opaque public slug per dashboard.

Revision ID: 20260830_dashboard_latest_share
Revises: 2757edbd890f
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_dashboard_latest_share"
down_revision: Union[str, None] = "2757edbd890f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_dashboard"
INDEX = "ix_dbgpt_dashboard_public_slug"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(TABLE)}
    if "public_slug" not in columns:
        op.add_column(TABLE, sa.Column("public_slug", sa.String(64), nullable=True))
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, ["public_slug"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes(TABLE)}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name=TABLE)
    columns = {item["name"] for item in inspector.get_columns(TABLE)}
    if "public_slug" in columns:
        op.drop_column(TABLE, "public_slug")
