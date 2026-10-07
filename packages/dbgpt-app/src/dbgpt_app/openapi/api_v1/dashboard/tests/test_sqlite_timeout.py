import time

import pytest

from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector


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
