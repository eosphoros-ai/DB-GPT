"""Add dashboard-scoped RBAC and an audit trail.

Revision ID: 20260811_dashboard_v21
Revises: 20260811_dashboard_v1
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260811_dashboard_v21"
down_revision: Union[str, None] = "20260811_dashboard_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_text():
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "dbgpt_dashboard_member" not in tables:
        op.create_table(
            "dbgpt_dashboard_member",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("dashboard_id", sa.String(length=64), nullable=False),
            sa.Column("principal_id", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=False),
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
            sa.UniqueConstraint(
                "dashboard_id",
                "principal_id",
                name="uk_dashboard_member_principal",
            ),
        )
        op.create_index(
            "ix_dbgpt_dashboard_member_dashboard_id",
            "dbgpt_dashboard_member",
            ["dashboard_id"],
        )
        op.create_index(
            "ix_dbgpt_dashboard_member_principal_id",
            "dbgpt_dashboard_member",
            ["principal_id"],
        )

    if "dbgpt_dashboard_audit" not in tables:
        audit_id_type = sa.Integer().with_variant(mysql.BIGINT(), "mysql")
        op.create_table(
            "dbgpt_dashboard_audit",
            sa.Column("id", audit_id_type, autoincrement=True, nullable=False),
            sa.Column("dashboard_id", sa.String(length=64), nullable=False),
            sa.Column("actor_id", sa.String(length=255), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=False),
            sa.Column("target_id", sa.String(length=255), nullable=True),
            sa.Column("details_json", _json_text(), nullable=False),
            sa.Column("request_id", sa.String(length=64), nullable=True),
            sa.Column(
                "gmt_created",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in (
            "dashboard_id",
            "actor_id",
            "action",
            "request_id",
            "gmt_created",
        ):
            op.create_index(
                f"ix_dbgpt_dashboard_audit_{column}",
                "dbgpt_dashboard_audit",
                [column],
            )

    # Backfill a canonical owner membership for databases created by v1.
    op.execute(
        sa.text(
            """
            INSERT INTO dbgpt_dashboard_member
                (dashboard_id, principal_id, role, created_by,
                 gmt_created, gmt_modified)
            SELECT d.id, d.owner_id, 'owner', d.owner_id,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM dbgpt_dashboard AS d
            WHERE NOT EXISTS (
                SELECT 1 FROM dbgpt_dashboard_member AS m
                WHERE m.dashboard_id = d.id AND m.principal_id = d.owner_id
            )
            """
        )
    )


def downgrade() -> None:
    tables = _tables()
    if "dbgpt_dashboard_audit" in tables:
        op.drop_table("dbgpt_dashboard_audit")
    if "dbgpt_dashboard_member" in tables:
        op.drop_table("dbgpt_dashboard_member")
