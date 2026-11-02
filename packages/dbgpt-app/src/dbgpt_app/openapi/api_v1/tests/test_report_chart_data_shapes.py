"""A captured row object is not an ECharts axis label or line value."""

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
    capture_sql_execution,
)
from dbgpt_app.openapi.api_v1.tools.report_chart_options import option_chart_spec
from dbgpt_app.openapi.api_v1.tools.report_charts import prepare_report_charts


def _source():
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid="chart-shape", run_id="turn-1")
    )
    artifact_id = capture_sql_execution(
        sql="SELECT month, gmv, orders FROM monthly",
        database="test",
        duration_ms=1,
        columns=["month", "gmv", "orders"],
        rows=[
            {"month": "2017-01", "gmv": 100, "orders": 2},
            {"month": "2017-02", "gmv": 120, "orders": 3},
        ],
        artifact_sink=sink,
    )
    rows = {"artifact_id": artifact_id, "path": ["rows"]}
    broken = {
        "caption": "月度趋势",
        "producer": {"artifact_id": artifact_id},
        "option": {
            "xAxis": {"type": "category", "data": rows},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "name": "GMV", "data": rows}],
        },
    }
    return sink, artifact_id, broken


def test_full_rows_in_axis_and_series_fall_back_to_captured_table():
    sink, artifact_id, broken = _source()
    with pytest.raises(ValueError, match="REPORT_CHART_DATA_SHAPE_INVALID"):
        option_chart_spec(broken, sink.snapshot())
    spec = {
        "sections": [
            {
                "heading": "月度趋势",
                "table": {
                    "artifact_id": artifact_id,
                    "columns": ["month", "gmv", "orders"],
                },
                "chart": broken,
            }
        ]
    }
    prepared = prepare_report_charts(spec, sink.snapshot(), sink)
    chart_ids = prepared["sections"][0]["chart"]["refs"]
    chart = next(
        item
        for item in sink.snapshot()
        if item.type == "chart" and item.artifact_id in chart_ids
    )
    option = chart.spec["option"]
    assert option["xAxis"][0]["data"] == ["2017-01", "2017-02"]
    assert all(
        isinstance(value, (int, float))
        for series in option["series"]
        for value in series["data"]
    )


def test_invalid_authored_chart_without_table_is_rejected():
    sink, _, broken = _source()
    with pytest.raises(ValueError, match="REPORT_CHART_DATA_SHAPE_INVALID"):
        prepare_report_charts(
            {"sections": [{"heading": "月度趋势", "chart": broken}]},
            sink.snapshot(),
            sink,
        )


def test_literal_chart_columns_resolve_only_exact_captured_values():
    sink, artifact_id, _ = _source()
    node = {
        "producer": {"artifact_id": artifact_id, "path": ["rows"]},
        "option": {
            "xAxis": {"type": "category", "data": ["2017-01", "2017-02"]},
            "series": [{"type": "bar", "data": [100, 120]}],
        },
    }
    result = option_chart_spec(node, sink.snapshot())
    assert result["option"]["series"][0]["data"] == [100, 120]
    assert {"artifact_id": artifact_id, "path": ["rows", 0, "gmv"]} in result[
        "source_references"
    ]
    node["option"]["series"][0]["data"] = [100, 121]
    with pytest.raises(ValueError, match="REPORT_CHART_OPTION_INVALID"):
        option_chart_spec(node, sink.snapshot())

    # Matching by value alone must not arbitrarily select between columns.
    ambiguous = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="ambiguous"))
    source = capture_sql_execution(
        sql="SELECT a, b FROM t",
        database="test",
        duration_ms=1,
        columns=["a", "b"],
        rows=[{"a": 1, "b": 1}, {"a": 2, "b": 2}],
        artifact_sink=ambiguous,
    )
    with pytest.raises(ValueError, match="REPORT_CHART_OPTION_INVALID"):
        option_chart_spec(
            {
                "producer": {"artifact_id": source, "path": ["rows"]},
                "option": {"series": [{"type": "bar", "data": [1, 2]}]},
            },
            ambiguous.snapshot(),
        )


def test_dataset_encode_with_object_rows_remains_valid():
    sink, artifact_id, _ = _source()
    option = {
        "producer": {"artifact_id": artifact_id},
        "option": {
            "xAxis": {"type": "category"},
            "yAxis": {"type": "value"},
            "series": [
                {"type": "line", "name": "GMV", "encode": {"x": "month", "y": "gmv"}}
            ],
        },
    }
    prepared = option_chart_spec(option, sink.snapshot())
    assert prepared["option"]["dataset"]["source"][0]["month"] == "2017-01"
    assert prepared["option"]["series"][0]["encode"]["y"] == "gmv"


def test_dataset_direct_result_reference_unwraps_captured_rows():
    sink, artifact_id, _ = _source()
    node = {
        "producer": {"artifact_id": artifact_id},
        "option": {
            "dataset": {"source": {"artifact_id": artifact_id}},
            "xAxis": {"type": "category"},
            "series": [{"type": "bar", "encode": {"x": "month", "y": "gmv"}}],
        },
    }
    result = option_chart_spec(node, sink.snapshot())
    source = result["option"]["dataset"]["source"]
    assert isinstance(source, list)
    assert source[0]["month"] == "2017-01"
    assert source[0]["gmv"] == 100
    assert {"artifact_id": artifact_id, "path": ["rows"]} in result["source_references"]


def test_dataset_ref_uses_matching_producer_selector():
    sink, artifact_id, _ = _source()
    node = {
        "producer": {"artifact_id": artifact_id, "path": ["rows"]},
        "option": {
            "dataset": {"source": {"$ref": artifact_id}},
            "xAxis": {"type": "category"},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "encode": {"x": "month", "y": "gmv"}}],
        },
    }
    result = option_chart_spec(node, sink.snapshot())
    assert result["option"]["dataset"]["source"][0]["gmv"] == 100
    node["option"]["dataset"]["source"]["$ref"] = "sql-unknown"
    with pytest.raises(ValueError, match="unknown or unsuccessful"):
        option_chart_spec(node, sink.snapshot())


def test_supplementary_chart_stays_with_its_section_before_conclusion():
    sink, first_id, _ = _source()
    second_id = capture_sql_execution(
        sql="SELECT region, total FROM regional",
        database="test",
        duration_ms=1,
        columns=["region", "total"],
        rows=[{"region": "A", "total": 7}, {"region": "B", "total": 9}],
        artifact_sink=sink,
    )
    spec = {
        "sections": [
            {
                "heading": "二、经营分析",
                "table": {"artifact_id": first_id, "columns": ["month", "gmv"]},
                "intro": [[{"artifact_id": second_id, "path": ["rows", 0, "total"]}]],
            },
            {"heading": "六、结论与建议"},
        ]
    }
    prepared = prepare_report_charts(spec, sink.snapshot(), sink)
    assert [section.get("heading") for section in prepared["sections"]] == [
        "二、经营分析",
        None,
        "六、结论与建议",
    ]
    assert all(section.get("chart") for section in prepared["sections"][:2])


def test_producer_alias_uses_declared_sql_rows_and_rejects_ambiguous_alias():
    sink, artifact_id, _ = _source()
    node = {
        "producer": {"artifact_id": artifact_id},
        "option": {
            "dataset": {"source": {"$ref": "producer"}},
            "series": [{"type": "bar", "encode": {"x": "month", "y": "gmv"}}],
        },
    }
    chart = option_chart_spec(node, sink.snapshot())
    assert chart["option"]["dataset"]["source"][0] == {
        "month": "2017-01",
        "gmv": 100,
        "orders": 2,
    }
    node["option"]["dataset"]["source"]["path"] = ["other"]
    with pytest.raises(ValueError, match="cannot override"):
        option_chart_spec(node, sink.snapshot())
    node["option"]["dataset"]["source"] = {"$ref": "producer"}
    del node["producer"]
    with pytest.raises(ValueError, match="requires an explicit producer"):
        option_chart_spec(node, sink.snapshot())


def test_relative_captured_paths_and_sql_column_projection():
    sink, sql_id, _ = _source()
    py_id = capture_python_execution(
        code="result = chart",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"chart": {"x": ["A", "B"], "series": [{"data": [10, 20]}]}},
        artifact_sink=sink,
    )
    python_chart = {
        "producer": {"artifact_id": py_id, "field": "chart"},
        "option": {
            "xAxis": {"type": "category", "data": {"$ref": "chart.x"}},
            "series": [{"type": "line", "data": {"$ref": "chart.series.0.data"}}],
        },
    }
    option = option_chart_spec(python_chart, sink.snapshot())["option"]
    assert option["xAxis"]["data"] == ["A", "B"]
    assert option["series"][0]["data"] == [10, 20]
    sql_chart = {
        "producer": {"artifact_id": sql_id, "field": "rows"},
        "option": {
            "xAxis": {"type": "category", "data": {"$ref": "rows.month"}},
            "series": [{"type": "bar", "data": {"$ref": "rows.gmv"}}],
        },
    }
    prepared = option_chart_spec(sql_chart, sink.snapshot())
    assert prepared["option"]["series"][0]["data"] == [100, 120]
    assert {"artifact_id": sql_id, "field": "rows", "path": [1, "gmv"]} in prepared[
        "source_references"
    ]
    sql_chart["option"]["series"][0]["data"]["$ref"] = "rows.missing"
    with pytest.raises(ValueError, match="projection field missing"):
        option_chart_spec(sql_chart, sink.snapshot())
