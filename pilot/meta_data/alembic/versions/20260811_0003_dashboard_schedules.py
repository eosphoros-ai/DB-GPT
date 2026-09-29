"""Add persistent, dashboard-scoped scheduled refreshes.

Revision ID: 20260811_dashboard_v22
Revises: 20260811_dashboard_v21
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260811_dashboard_v22"
down_revision: Union[str, None] = "20260811_dashboard_v21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TASK_TABLE = "dbgpt_serve_scheduled_task"
RUN_TABLE = "dbgpt_serve_scheduled_run"


def _inspector():
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {
        index["name"]
        for index in _inspector().get_indexes(table_name)
        if index.get("name")
    }


def _unique_constraints(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in _inspector().get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _json_text():
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


def _create_task_table() -> None:
    op.create_table(
        TASK_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("task_name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "task_type",
            sa.String(length=32),
            server_default="chat_replay",
            nullable=False,
        ),
        sa.Column("cron_expression", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column("user_name", sa.String(length=128), nullable=True),
        sa.Column("owner_id", sa.String(length=255), nullable=True),
        sa.Column("sys_code", sa.String(length=128), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uk_scheduled_task_task_id"),
    )


def _create_run_table() -> None:
    op.create_table(
        RUN_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("output_conv_uid", sa.String(length=64), nullable=True),
        sa.Column("output_resource_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("result_json", _json_text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uk_scheduled_run_run_id"),
        sa.UniqueConstraint(
            "task_id", "idempotency_key", name="uk_scheduled_run_idempotency"
        ),
    )


def _add_missing_columns(table_name: str, definitions: dict[str, sa.Column]) -> None:
    present = _columns(table_name)
    for name, column in definitions.items():
        if name not in present:
            op.add_column(table_name, column)


def _create_indexes() -> None:
    task_indexes = _indexes(TASK_TABLE)
    for name, columns in {
        "ix_dbgpt_serve_scheduled_task_task_type": ["task_type"],
        "ix_dbgpt_serve_scheduled_task_user_name": ["user_name"],
        "ix_dbgpt_serve_scheduled_task_owner_id": ["owner_id"],
        "ix_dbgpt_serve_scheduled_task_resource_type": ["resource_type"],
        "ix_dbgpt_serve_scheduled_task_resource_id": ["resource_id"],
        "ix_dbgpt_serve_scheduled_task_lease_expires_at": ["lease_expires_at"],
    }.items():
        if name not in task_indexes:
            op.create_index(name, TASK_TABLE, columns)

    run_indexes = _indexes(RUN_TABLE)
    for name, columns in {
        "ix_dbgpt_serve_scheduled_run_task_id": ["task_id"],
        "ix_dbgpt_serve_scheduled_run_started_at": ["started_at"],
    }.items():
        if name not in run_indexes:
            op.create_index(name, RUN_TABLE, columns)


def upgrade() -> None:
    if TASK_TABLE not in _tables():
        _create_task_table()
    else:
        _add_missing_columns(
            TASK_TABLE,
            {
                "owner_id": sa.Column("owner_id", sa.String(length=255)),
                "resource_type": sa.Column("resource_type", sa.String(length=64)),
                "resource_id": sa.Column("resource_id", sa.String(length=128)),
                "lease_owner": sa.Column("lease_owner", sa.String(length=64)),
                "lease_expires_at": sa.Column("lease_expires_at", sa.DateTime()),
            },
        )

    if RUN_TABLE not in _tables():
        _create_run_table()
    else:
        _add_missing_columns(
            RUN_TABLE,
            {
                "output_resource_id": sa.Column(
                    "output_resource_id", sa.String(length=255)
                ),
                "attempt_count": sa.Column(
                    "attempt_count",
                    sa.Integer(),
                    server_default="1",
                    nullable=False,
                ),
                "result_json": sa.Column("result_json", _json_text()),
                "idempotency_key": sa.Column("idempotency_key", sa.String(length=128)),
            },
        )

    # Legacy chat schedules predate authenticated owner IDs. The backfill keeps
    # them manageable while all newly-created tasks require the current actor ID.
    op.execute(
        sa.text(
            f"UPDATE {TASK_TABLE} "
            "SET owner_id = COALESCE(NULLIF(user_name, ''), '001') "
            "WHERE owner_id IS NULL OR owner_id = ''"
        )
    )

    if (
        "uk_scheduled_run_idempotency" not in _unique_constraints(RUN_TABLE)
        and op.get_bind().dialect.name != "sqlite"
    ):
        op.create_unique_constraint(
            "uk_scheduled_run_idempotency",
            RUN_TABLE,
            ["task_id", "idempotency_key"],
        )
    elif (
        "uk_scheduled_run_idempotency" not in _unique_constraints(RUN_TABLE)
        and op.get_bind().dialect.name == "sqlite"
    ):
        # SQLite cannot add constraints directly, so Alembic recreates the table.
        with op.batch_alter_table(RUN_TABLE) as batch:
            batch.create_unique_constraint(
                "uk_scheduled_run_idempotency", ["task_id", "idempotency_key"]
            )

    _create_indexes()


def downgrade() -> None:
    # Existing scheduled-chat rows may depend on these tables, so downgrade only
    # removes v2.2 additions instead of deleting the whole scheduler subsystem.
    if RUN_TABLE in _tables():
        unique_names = _unique_constraints(RUN_TABLE)
        columns = _columns(RUN_TABLE)
        with op.batch_alter_table(RUN_TABLE) as batch:
            if "uk_scheduled_run_idempotency" in unique_names:
                batch.drop_constraint("uk_scheduled_run_idempotency", type_="unique")
            for name in (
                "output_resource_id",
                "attempt_count",
                "result_json",
                "idempotency_key",
            ):
                if name in columns:
                    batch.drop_column(name)

    if TASK_TABLE in _tables():
        columns = _columns(TASK_TABLE)
        with op.batch_alter_table(TASK_TABLE) as batch:
            for name in (
                "owner_id",
                "resource_type",
                "resource_id",
                "lease_owner",
                "lease_expires_at",
            ):
                if name in columns:
                    batch.drop_column(name)
