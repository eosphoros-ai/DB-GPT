"""Shared resources must preserve connector-specific run() adaptations."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from dbgpt.agent.resource.database import RDBMSConnectorResource
from dbgpt_ext.datasource.conn_spark import SparkConnector
from dbgpt_ext.datasource.rdbms.conn_clickhouse import ClickhouseConnector
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector


@pytest.fixture(params=["clickhouse", "spark"])
def adapted_resource(request):
    rows = [(1, 100), (2, 200)]
    if request.param == "clickhouse":
        client = MagicMock()
        client.database = "test"
        client.query.side_effect = lambda sql: SimpleNamespace(
            result_rows=list(rows), column_names=("id", "sales")
        )
        connector = ClickhouseConnector(client, engine="MergeTree")
        # This is how the native connector is constructed: no SQLAlchemy state.
        assert not hasattr(connector, "_db_sessions")
    else:
        # Exercise Spark's real run/query_ex methods without requiring a JVM.
        connector = object.__new__(SparkConnector)
        connector.table_name = "sales"
        connector.df = MagicMock()
        connector.spark_session = MagicMock()
        result = connector.spark_session.sql.return_value
        result.first.return_value.asDict.return_value = {"id": 1, "sales": 100}
        result.collect.return_value = list(rows)
        columns, raw = connector.query_ex("SELECT id, sales FROM sales")
        assert len(raw) == 3  # Spark query_ex includes its column header.
        assert list(columns) == ["id", "sales"]

    with ThreadPoolExecutor(max_workers=1) as executor:
        yield RDBMSConnectorResource(
            "test",
            connector=connector,
            db_name="test",
            dialect=request.param,
            executor=executor,
        )


@pytest.mark.asyncio
async def test_async_query_preserves_native_adapter(adapted_resource):
    sql = "SELECT id, sales FROM sales"
    expected_columns, expected_rows = adapted_resource.execute(sql=sql)
    columns, rows = await adapted_resource.query(sql)
    assert list(columns) == list(expected_columns) == ["id", "sales"]
    assert rows == expected_rows == [(1, 100), (2, 200)]


@pytest.mark.asyncio
async def test_query_to_dataframe_does_not_include_header(adapted_resource):
    frame = await adapted_resource.query_to_df("SELECT id, sales FROM sales")
    assert frame.to_dict(orient="records") == [
        {"id": 1, "sales": 100},
        {"id": 2, "sales": 200},
    ]


@pytest.mark.asyncio
async def test_sqlite_query_and_source_cancellation_still_work(tmp_path):
    connector = SQLiteConnector.from_file_path(str(tmp_path / "query.db"))
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            resource = RDBMSConnectorResource(
                "sqlite", connector=connector, executor=executor
            )
            columns, rows = await resource.query("SELECT 42 AS answer")
            assert list(columns) == ["answer"]
            assert [tuple(row) for row in rows] == [(42,)]
            with pytest.raises(TimeoutError, match="SQL_QUERY_TIMEOUT"):
                await resource.query(
                    "WITH RECURSIVE counter(x) AS (SELECT 0 UNION ALL "
                    "SELECT x + 1 FROM counter WHERE x < 1000000000) "
                    "SELECT sum(x) FROM counter",
                    timeout=0.05,
                )
            # A single worker can run this only after the cancelled SQL exits.
            _, rows = await resource.query("SELECT 7", timeout=2)
            assert [tuple(row) for row in rows] == [(7,)]
    finally:
        connector.close()


@pytest.mark.asyncio
async def test_sqlite_subclass_run_override_is_preserved():
    class AdaptedSQLite(SQLiteConnector):
        def run(self, command, fetch="all"):
            return [("adapted",), (123,)]

        def query_ex(self, *args, **kwargs):
            raise AssertionError("Must use the connector's run override")

    connector = object.__new__(AdaptedSQLite)
    connector._is_closed = True  # Synthetic adapter owns no database handles.
    with ThreadPoolExecutor(max_workers=1) as executor:
        resource = RDBMSConnectorResource(
            "adapted",
            connector=connector,
            db_name="test",
            dialect="sqlite",
            executor=executor,
        )
        assert await resource.query("SELECT 1") == (("adapted",), [(123,)])
