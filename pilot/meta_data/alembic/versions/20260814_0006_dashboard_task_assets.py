"""Link dashboards to task turns and distinguish generated drafts from assets.

Revision ID: 20260814_dashboard_task_assets
Revises: 20260812_dashboard_v27
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_dashboard_task_assets"
down_revision: Union[str, Sequence[str], None] = "20260812_dashboard_v27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_dashboard"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns(TABLE)}
    with op.batch_alter_table(TABLE) as batch:
        if "source_turn_id" not in existing:
            batch.add_column(sa.Column("source_turn_id", sa.String(64), nullable=True))
        if "origin" not in existing:
            batch.add_column(
                sa.Column(
                    "origin",
                    sa.String(32),
                    nullable=False,
                    server_default="manual",
                )
            )
        if "asset_state" not in existing:
            batch.add_column(
                sa.Column(
                    "asset_state",
                    sa.String(32),
                    nullable=False,
                    server_default="saved",
                )
            )
        if "saved_at" not in existing:
            batch.add_column(sa.Column("saved_at", sa.DateTime(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE dbgpt_dashboard SET saved_at = gmt_modified "
            "WHERE asset_state = 'saved' AND saved_at IS NULL"
        )
    )
    # The two bundled, immutable regression examples are templates, not user
    # assets.  Existing local demo databases predate the lifecycle columns, so
    # classify their stable IDs during migration as well.
    op.execute(
        sa.text(
            "UPDATE dbgpt_dashboard SET origin = 'template' "
            "WHERE id IN ('walmart-sales-demo', 'apple-financial-demo')"
        )
    )

    existing_indexes = {
        item["name"] for item in sa.inspect(op.get_bind()).get_indexes(TABLE)
    }
    for name, column in (
        ("ix_dbgpt_dashboard_source_turn_id", "source_turn_id"),
        ("ix_dbgpt_dashboard_origin", "origin"),
        ("ix_dbgpt_dashboard_asset_state", "asset_state"),
        ("ix_dbgpt_dashboard_saved_at", "saved_at"),
    ):
        if name not in existing_indexes:
            op.create_index(name, TABLE, [column])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    existing_indexes = {item["name"] for item in inspector.get_indexes(TABLE)}
    for name in (
        "ix_dbgpt_dashboard_saved_at",
        "ix_dbgpt_dashboard_asset_state",
        "ix_dbgpt_dashboard_origin",
        "ix_dbgpt_dashboard_source_turn_id",
    ):
        if name in existing_indexes:
            op.drop_index(name, table_name=TABLE)
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    with op.batch_alter_table(TABLE) as batch:
        for column in ("saved_at", "asset_state", "origin", "source_turn_id"):
            if column in existing:
                batch.drop_column(column)
