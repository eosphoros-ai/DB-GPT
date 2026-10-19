"""Run native chart tools against a real local Spark JVM (no Spark mocks)."""

import json
import os
import re
import sys

import pytest

if os.environ.get("DBGPT_RUN_LIVE_REGRESSIONS") != "1":
    pytest.skip(
        "Requires the explicitly enabled live Spark environment",
        allow_module_level=True,
    )

if os.environ.get("DBGPT_SPARK_PYTHON_PATH"):
    sys.path.append(os.environ["DBGPT_SPARK_PYTHON_PATH"])

from pyspark.sql import SparkSession

from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
)
from dbgpt_app.openapi.api_v1.tools.chart_query import make_chart_query
from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query
from dbgpt_ext.datasource.conn_spark import SparkConnector


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("dbgpt-F19-real-regression")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("capture", [False, True])
async def test_public_spark_sql_and_native_chart(spark, tmp_path, capture):
    csv = tmp_path / "sales.csv"
    csv.write_text("bucket,amount\nA,1\nA,2\nB,4\n", encoding="utf-8")
    connector = SparkConnector(csv.as_uri(), spark_session=spark)
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="real-spark"))
    state = {"_report_artifact_sink": sink} if capture else {}
    chart = make_chart_query(state, connector)
    sql = make_sql_query(state, connector)
    pack = ToolPack([chart._tool, sql._tool])
    query = (
        "SELECT bucket, SUM(amount) AS total FROM temp GROUP BY bucket ORDER BY bucket"
    )
    plain = json.loads(await pack.async_execute(resource_name="sql_query", sql=query))
    assert plain.get("success") is not False, plain
    result = json.loads(
        await pack.async_execute(
            resource_name="chart_query",
            sql=query,
            display_type="response_bar_chart",
            thought="Real Spark aggregation",
        )
    )
    assert result.get("success") is not False, result
    assert connector.get_current_db_name() == spark.catalog.currentDatabase()
    rendered = "\n".join(str(c.get("content", "")) for c in result["chunks"])
    match = re.search(r"```vis-db-chart\s*(\{.*?\})\s*```", rendered, re.S)
    assert match, rendered
    spec = json.loads(match.group(1))
    assert spec["data"] == [{"bucket": "A", "total": 3}, {"bucket": "B", "total": 4}], (
        spec
    )
    if capture:
        chart_artifact = next(a for a in sink.snapshot() if a.type == "chart")
        source = next(
            a
            for a in sink.snapshot()
            if a.artifact_id in chart_artifact.input_artifact_ids
        )
        assert chart_artifact.status == source.status == "succeeded"
        assert source.database == spark.catalog.currentDatabase()
    else:
        assert not sink.snapshot()
