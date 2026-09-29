"""Store immutable schema snapshots for every dashboard edit revision.

Revision ID: 20260831_dashboard_edit_versions
Revises: 20260831_upload_dataset_registry
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260831_dashboard_edit_versions"
down_revision: Union[str, None] = "20260831_upload_dataset_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_dashboard_edit_version"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column(
                "id",
                sa.Integer().with_variant(sa.BigInteger(), "mysql"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("dashboard_id", sa.String(64), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column(
                "schema_json",
                sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
                nullable=False,
            ),
            sa.Column(
                "source", sa.String(64), nullable=False, server_default="migration"
            ),
            sa.Column("actor_id", sa.String(255), nullable=False),
            sa.Column("operation_id", sa.String(64), nullable=True),
            sa.Column("gmt_created", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "dashboard_id", "revision", name="uk_dashboard_edit_version"
            ),
        )
        op.create_index(
            "ix_dbgpt_dashboard_edit_version_dashboard_id",
            TABLE,
            ["dashboard_id"],
        )
        op.create_index(
            "ix_dbgpt_dashboard_edit_version_source", TABLE, ["source"]
        )
        op.create_index(
            "ix_dbgpt_dashboard_edit_version_actor_id", TABLE, ["actor_id"]
        )
        op.create_index(
            "ix_dbgpt_dashboard_edit_version_operation_id",
            TABLE,
            ["operation_id"],
        )
        op.create_index(
            "ix_dbgpt_dashboard_edit_version_gmt_created",
            TABLE,
            ["gmt_created"],
        )

    dashboard = sa.table(
        "dbgpt_dashboard",
        sa.column("id", sa.String(64)),
        sa.column("current_revision", sa.Integer()),
        sa.column("schema_json", sa.Text()),
        sa.column("owner_id", sa.String(255)),
        sa.column("gmt_modified", sa.DateTime()),
    )
    edit_version = sa.table(
        TABLE,
        sa.column("dashboard_id", sa.String(64)),
        sa.column("revision", sa.Integer()),
        sa.column("schema_json", sa.Text()),
        sa.column("source", sa.String(64)),
        sa.column("actor_id", sa.String(255)),
        sa.column("operation_id", sa.String(64)),
        sa.column("gmt_created", sa.DateTime()),
    )
    connection.execute(
        sa.insert(edit_version).from_select(
            [
                "dashboard_id",
                "revision",
                "schema_json",
                "source",
                "actor_id",
                "operation_id",
                "gmt_created",
            ],
            sa.select(
                dashboard.c.id,
                dashboard.c.current_revision,
                dashboard.c.schema_json,
                sa.literal("migration"),
                dashboard.c.owner_id,
                sa.null(),
                dashboard.c.gmt_modified,
            ).where(
                ~sa.exists(
                    sa.select(1)
                    .select_from(edit_version)
                    .where(
                        edit_version.c.dashboard_id == dashboard.c.id,
                        edit_version.c.revision == dashboard.c.current_revision,
                    )
                )
            ),
        )
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in inspector.get_table_names():
        op.drop_table(TABLE)
