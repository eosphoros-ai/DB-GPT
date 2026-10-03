"""Register owned multi-file upload datasets without exposing server paths.

Revision ID: 20260831_upload_dataset_registry
Revises: 20260831_dashboard_ai_intent
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260831_upload_dataset_registry"
down_revision: Union[str, None] = "20260831_dashboard_ai_intent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_uploaded_dataset"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in inspector.get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("dataset_id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("database_name", sa.String(255), nullable=False),
        sa.Column("database_path", sa.Text(), nullable=False),
        sa.Column("batch_dir", sa.Text(), nullable=False),
        sa.Column(
            "manifest_json",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column(
            "relationships_json",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("gmt_created", sa.DateTime(), nullable=False),
        sa.Column("gmt_modified", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("database_name", name="uk_uploaded_dataset_database"),
    )
    op.create_index("ix_uploaded_dataset_owner", TABLE, ["owner_id"])
    op.create_index(
        "ix_uploaded_dataset_conversation", TABLE, ["conversation_id"]
    )
    op.create_index("ix_uploaded_dataset_database", TABLE, ["database_name"])
    op.create_index("ix_uploaded_dataset_status", TABLE, ["status"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in inspector.get_table_names():
        op.drop_table(TABLE)
