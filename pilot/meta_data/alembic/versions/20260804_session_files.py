"""Create owner-bound session file metadata.

Revision ID: 20260804sf01
Revises: 015827d5a9d0
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260804sf01"
down_revision: Union[str, None] = "015827d5a9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the session file table and its lookup indexes."""
    op.create_table(
        "dbgpt_session_file",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("storage_uri", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("file_kind", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "inspection_json",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_file_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(session_id IS NULL) <> (task_id IS NULL)",
            name="ck_session_file_scope",
        ),
    )
    op.create_index(
        "uk_session_file_file_id",
        "dbgpt_session_file",
        ["file_id"],
        unique=True,
    )
    op.create_index(
        "idx_session_file_owner_session",
        "dbgpt_session_file",
        ["owner_id", "session_id", "ordinal"],
    )
    op.create_index(
        "idx_session_file_owner_task",
        "dbgpt_session_file",
        ["owner_id", "task_id", "ordinal"],
    )
    op.create_index(
        "idx_session_file_sha256",
        "dbgpt_session_file",
        ["owner_id", "sha256"],
    )


def downgrade() -> None:
    """Drop the session file table and its indexes."""
    op.drop_table("dbgpt_session_file")
