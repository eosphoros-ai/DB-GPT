"""Run the distributed MySQL SQL against an explicitly disposable test database."""

import os
import re
import uuid
from pathlib import Path

import pytest
from pymysql.constants import CLIENT
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from dbgpt.storage.metadata import Model
from dbgpt_app.initialization.db_model_initialization import _MODELS  # noqa: F401

pytestmark = pytest.mark.mysql_integration
ROOT = Path(__file__).parents[8]
SCHEMA = ROOT / "assets/schema/dbgpt.sql"
FULL = ROOT / "assets/schema/upgrade/dashboard/dashboard.sql"
UPGRADE = ROOT / "assets/schema/upgrade/dashboard/upgrade_to_dashboard.sql"
LEGACY = ROOT / "assets/schema/upgrade/v0_8_2/v0.8.2.sql"


def _execute(engine, sql, example_database):
    # Keep USE statements: otherwise tables created in EXAMPLE_1 by mistake
    # would pass this test. Only redirect database names into disposable DBs.
    database = engine.url.database
    names = {"dbgpt": database, "example_1": example_database}
    sql = re.sub(
        r"(?im)\b(CREATE\s+DATABASE\s+IF\s+NOT\s+EXISTS|USE)\s+"
        r"`?(dbgpt|EXAMPLE_1)`?\s*;",
        lambda match: f"{match[1]} `{names[match[2].lower()]}`;",
        sql,
    )
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"USE `{database}`")
            cursor.execute(sql)
            while cursor.nextset():
                pass
            cursor.execute(f"USE `{database}`")
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def mysql_schema_engine():
    url = os.getenv("DASHBOARD_TEST_MYSQL_URL")
    if not url:
        pytest.skip("DASHBOARD_TEST_MYSQL_URL is not configured")
    database = make_url(url).database
    if (
        not database
        or "test" not in database.lower()
        or not re.fullmatch(r"[a-zA-Z0-9_]+", database)
    ):
        pytest.fail("The disposable MySQL database name must contain 'test'")
    engine = create_engine(url, connect_args={"client_flag": CLIENT.MULTI_STATEMENTS})
    example_database = f"dashboard_test_example_{uuid.uuid4().hex[:12]}"

    def reset():
        names = inspect(engine).get_table_names(schema=database)
        with engine.begin() as connection:
            for name in reversed(names):
                connection.execute(text(f"DROP TABLE `{database}`.`{name}`"))
            connection.execute(text(f"DROP DATABASE IF EXISTS `{example_database}`"))

    reset()
    try:
        yield engine, example_database, reset
    finally:
        reset()
        engine.dispose()


def _schema_shape(engine):
    inspector = inspect(engine)
    return {
        name: {
            "columns": sorted(
                (
                    column["name"],
                    str(column["type"]),
                    column["nullable"],
                    column["default"],
                )
                for column in inspector.get_columns(name)
            ),
            "indexes": sorted(
                (index["name"], tuple(index["column_names"]), index["unique"])
                for index in inspector.get_indexes(name)
            ),
            "primary_key": inspector.get_pk_constraint(name)["constrained_columns"],
        }
        for name in inspector.get_table_names()
    }


@pytest.mark.parametrize("full_schema", [SCHEMA, FULL], ids=["canonical", "release"])
def test_mysql_sql_initializes_and_upgrades_without_identity_backfill(
    mysql_schema_engine, full_schema
):
    assert FULL.read_bytes() == SCHEMA.read_bytes()
    engine, example_database, reset = mysql_schema_engine
    _execute(engine, LEGACY.read_text(encoding="utf-8"), example_database)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO dbgpt_serve_scheduled_task "
                "(task_id, task_name, user_name, cron_expression, payload_json) "
                "VALUES ('legacy', 'Existing task', 'Display name', "
                "'* * * * *', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO dbgpt_serve_scheduled_run "
                "(run_id, task_id, started_at, status) "
                "VALUES ('old-run', 'legacy', NOW(), 'success')"
            )
        )
    _execute(engine, UPGRADE.read_text(encoding="utf-8"), example_database)
    inspector = inspect(engine)
    for table in Model.metadata.tables.values():
        if table.name.startswith("dbgpt_dashboard") or table.name in {
            "dbgpt_uploaded_dataset",
            "dbgpt_serve_scheduled_task",
            "dbgpt_serve_scheduled_run",
            "chat_history_message",
        }:
            assert {column.name for column in table.columns} == {
                column["name"] for column in inspector.get_columns(table.name)
            }
    assert any(
        item["column_names"] == ["task_id", "idempotency_key"]
        for item in inspector.get_unique_constraints("dbgpt_serve_scheduled_run")
    )
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT user_name, owner_id FROM dbgpt_serve_scheduled_task "
                "WHERE task_id='legacy'"
            )
        ).one() == ("Display name", None)
        assert connection.execute(
            text(
                "SELECT status, attempt_count FROM dbgpt_serve_scheduled_run "
                "WHERE run_id='old-run'"
            )
        ).one() == ("success", 1)
    upgraded = _schema_shape(engine)
    reset()
    _execute(engine, full_schema.read_text(encoding="utf-8"), example_database)
    assert _schema_shape(engine) == upgraded
    assert inspect(engine).get_table_names(schema=example_database) == ["users"]
