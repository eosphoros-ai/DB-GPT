"""Run the distributed MySQL SQL against an explicitly disposable test database."""

import os
import re
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
UPGRADE = ROOT / "assets/schema/upgrade/dashboard/upgrade.sql"
LEGACY = Path(__file__).parent / "fixtures/legacy_mysql_schema.sql"


def _execute(engine, sql):
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            while cursor.nextset():
                pass
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def mysql_schema_engine():
    url = os.getenv("DASHBOARD_TEST_MYSQL_URL")
    if not url:
        pytest.skip("DASHBOARD_TEST_MYSQL_URL is not configured")
    database = make_url(url).database
    if not database or "test" not in database.lower():
        pytest.fail("The disposable MySQL database name must contain 'test'")
    engine = create_engine(url, connect_args={"client_flag": CLIENT.MULTI_STATEMENTS})
    names = re.findall(
        r"CREATE TABLE IF NOT EXISTS\s+`?(\w+)", SCHEMA.read_text(encoding="utf-8")
    )

    def reset():
        with engine.begin() as connection:
            for name in reversed(names):
                connection.execute(text(f"DROP TABLE IF EXISTS `{name}`"))

    reset()
    try:
        yield engine
    finally:
        reset()
        engine.dispose()


@pytest.mark.parametrize("existing", [False, True])
def test_mysql_sql_initializes_and_upgrades_without_identity_backfill(
    mysql_schema_engine, existing
):
    engine = mysql_schema_engine
    if existing:
        _execute(engine, LEGACY.read_text(encoding="utf-8"))
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
    else:
        sql = SCHEMA.read_text(encoding="utf-8")
        # Execute the shipped table definitions in the selected disposable DB.
        sql = re.sub(r"(?im)^CREATE\s+DATABASE\b[^;]*;", "", sql)
        sql = re.sub(r"(?im)^\s*use\s+dbgpt\s*;", "", sql)
        _execute(engine, sql)
    for _ in range(2):
        _execute(engine, UPGRADE.read_text(encoding="utf-8"))
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
    if existing:
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
