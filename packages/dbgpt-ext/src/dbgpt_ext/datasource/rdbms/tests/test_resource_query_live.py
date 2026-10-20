"""Opt-in integration tests against ClickHouse and a real local Spark JVM.

Set DBGPT_TEST_LIVE_CONNECTORS=1, F04_CLICKHOUSE_HOST/PORT/USER/PASSWORD,
and install datasource_clickhouse/datasource_spark extras before running.
ClickHouse uses its existing system.numbers table; no server data is modified.
Spark reads a temporary CSV and stops its own session after the tests.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from dbgpt.agent.resource.database import RDBMSConnectorResource

pytestmark = pytest.mark.skipif(
    os.getenv("DBGPT_TEST_LIVE_CONNECTORS") != "1",
    reason="Opt-in test: requires ClickHouse and Java/Spark",
)


@pytest.fixture(scope="module", params=["clickhouse", "spark"])
def live_resource(request, tmp_path_factory):
    session = client = None
    if request.param == "clickhouse":
        from dbgpt_ext.datasource.rdbms.conn_clickhouse import ClickhouseConnector

        connector = ClickhouseConnector.from_uri_db(
            host=os.environ.get("F04_CLICKHOUSE_HOST", "127.0.0.1"),
            port=int(os.environ["F04_CLICKHOUSE_PORT"]),
            user=os.environ["F04_CLICKHOUSE_USER"],
            pwd=os.environ["F04_CLICKHOUSE_PASSWORD"],
            db_name="default",
        )
        client = connector.client
        request.addfinalizer(client.close)
        sql = "SELECT toInt64(number + 1) AS id, toInt64((number + 1) * 100) "
        sql += "AS sales FROM system.numbers LIMIT 2"
        assert not hasattr(connector, "_db_sessions")
    else:
        from pyspark.sql import SparkSession

        from dbgpt_ext.datasource.conn_spark import SparkConnector

        session = (
            SparkSession.builder.master("local[1]")
            .appName("dbgpt-f04-live-test")
            .config("spark.ui.enabled", "false")
            .config("spark.driver.bindAddress", "127.0.0.1")
            .getOrCreate()
        )
        request.addfinalizer(session.stop)
        session.sparkContext.setLogLevel("ERROR")
        path = tmp_path_factory.mktemp("f04-spark") / "sales.csv"
        path.write_text("id,sales\n1,100\n2,200\n", encoding="utf-8")
        connector = SparkConnector(str(path), spark_session=session)
        sql = "SELECT id, sales FROM temp ORDER BY id"
    with ThreadPoolExecutor(max_workers=1) as executor:
        resource = RDBMSConnectorResource(
            "f04-live",
            connector=connector,
            db_name="default",
            dialect=request.param,
            executor=executor,
        )
        yield resource, sql


@pytest.mark.asyncio
async def test_live_query_matches_native_run(live_resource):
    resource, sql = live_resource
    native = resource.connector.run(sql)
    columns, rows = await resource.query(sql)
    assert list(columns) == list(native[0]) == ["id", "sales"]
    assert [tuple(row) for row in rows] == [tuple(row) for row in native[1:]]
    assert [tuple(row) for row in rows] == [(1, 100), (2, 200)]


@pytest.mark.asyncio
async def test_live_async_execute(live_resource):
    resource, sql = live_resource
    columns, rows = await resource.async_execute(sql=sql)
    assert list(columns) == ["id", "sales"]
    assert [tuple(row) for row in rows] == [(1, 100), (2, 200)]


@pytest.mark.asyncio
async def test_live_dataframe_contains_only_data(live_resource):
    resource, sql = live_resource
    frame = await resource.query_to_df(sql)
    assert frame.to_dict(orient="records") == [
        {"id": 1, "sales": 100},
        {"id": 2, "sales": 200},
    ]
