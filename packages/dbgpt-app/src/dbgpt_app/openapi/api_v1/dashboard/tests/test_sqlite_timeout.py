import logging
import sqlite3
import time

import pytest

from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector


@pytest.mark.parametrize("fetch", ["all", "one"])
def test_sqlite_query_without_progress_handler_executes_with_warning(caplog, fetch):
    class ConnectionWithoutProgressHandler(sqlite3.Connection):
        @property
        def set_progress_handler(self):
            raise AttributeError("set_progress_handler")

    connector = SQLiteConnector.from_uri(
        "sqlite://",
        engine_args={"connect_args": {"factory": ConnectionWithoutProgressHandler}},
    )
    try:
        with caplog.at_level(logging.WARNING, logger="dbgpt.datasource.rdbms.base"):
            fields, rows = connector.query_ex(
                "SELECT :first AS value UNION ALL SELECT :second AS value",
                params={"first": 7, "second": 9},
                fetch=fetch,
                timeout=0.001,
            )
        assert fields == ["value"]
        assert [row[0] for row in rows] == ([7, 9] if fetch == "all" else [7])
        assert "proceeding without timeout" in caplog.text
    finally:
        connector.close()


def test_sqlite_query_timeout_interrupts_and_resets(tmp_path):
    connector = SQLiteConnector.from_file_path(str(tmp_path / "timeout-test.db"))
    slow_query = """
        WITH RECURSIVE counter(value) AS (
            SELECT 1
            UNION ALL
            SELECT value + 1 FROM counter WHERE value < 100000000
        )
        SELECT SUM(value) AS total FROM counter
    """

    started_at = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match="exceeded timeout"):
            connector.query_ex(slow_query, timeout=0.001)
        assert time.monotonic() - started_at < 2

        fields, rows = connector.query_ex("SELECT 1 AS value", timeout=0.5)
        assert fields == ["value"]
        assert rows[0][0] == 1
    finally:
        connector.close()
