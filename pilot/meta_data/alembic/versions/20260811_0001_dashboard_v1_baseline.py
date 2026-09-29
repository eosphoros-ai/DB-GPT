"""Establish the Dashboard v1 persistence baseline.

Revision ID: 20260811_dashboard_v1
Revises: None
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260811_dashboard_v1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_text():
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Create v1 tables if they were not already created by an early preview."""

    tables = _tables()
    if "dbgpt_dashboard" not in tables:
        op.create_table(
            "dbgpt_dashboard",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("owner_id", sa.String(length=255), nullable=False),
            sa.Column("conversation_id", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("data_source_id", sa.String(length=255), nullable=False),
            sa.Column("schema_json", _json_text(), nullable=False),
            sa.Column("current_revision", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column(
                "gmt_created",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "gmt_modified",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_dbgpt_dashboard_owner_id", "dbgpt_dashboard", ["owner_id"])
        op.create_index(
            "ix_dbgpt_dashboard_conversation_id",
            "dbgpt_dashboard",
            ["conversation_id"],
        )

    if "dbgpt_dashboard_revision" not in tables:
        op.create_table(
            "dbgpt_dashboard_revision",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dashboard_id", sa.String(length=64), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("schema_json", _json_text(), nullable=False),
            sa.Column("snapshot_json", _json_text(), nullable=False),
            sa.Column("validation_json", _json_text(), nullable=False),
            sa.Column("share_token_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "gmt_published",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "dashboard_id",
                "revision",
                name="uk_dashboard_published_revision",
            ),
            sa.UniqueConstraint(
                "share_token_hash", name="uk_dashboard_share_token_hash"
            ),
        )
        op.create_index(
            "ix_dbgpt_dashboard_revision_dashboard_id",
            "dbgpt_dashboard_revision",
            ["dashboard_id"],
        )
        op.create_index(
            "ix_dbgpt_dashboard_revision_share_token_hash",
            "dbgpt_dashboard_revision",
            ["share_token_hash"],
        )


def downgrade() -> None:
    tables = _tables()
    if "dbgpt_dashboard_revision" in tables:
        op.drop_table("dbgpt_dashboard_revision")
    if "dbgpt_dashboard" in tables:
        op.drop_table("dbgpt_dashboard")
