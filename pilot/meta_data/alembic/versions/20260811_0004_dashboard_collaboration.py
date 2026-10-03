"""Add durable dashboard collaboration operations.

Revision ID: 20260811_dashboard_v24
Revises: 20260811_dashboard_v22
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260811_dashboard_v24"
down_revision: Union[str, None] = "20260811_dashboard_v22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "dbgpt_dashboard_operation"


def _json_text():
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column(
            "id",
            sa.Integer().with_variant(mysql.BIGINT(), "mysql"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("dashboard_id", sa.String(length=64), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("applied_revision", sa.Integer(), nullable=False),
        sa.Column("patch_json", _json_text(), nullable=False),
        sa.Column(
            "gmt_created", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dashboard_id", "operation_id", name="uk_dashboard_operation_id"
        ),
        sa.UniqueConstraint(
            "dashboard_id",
            "applied_revision",
            name="uk_dashboard_operation_revision",
        ),
    )
    op.create_index(
        "ix_dbgpt_dashboard_operation_dashboard_id", TABLE, ["dashboard_id"]
    )
    op.create_index("ix_dbgpt_dashboard_operation_client_id", TABLE, ["client_id"])
    op.create_index("ix_dbgpt_dashboard_operation_actor_id", TABLE, ["actor_id"])
    op.create_index("ix_dbgpt_dashboard_operation_gmt_created", TABLE, ["gmt_created"])


def downgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
