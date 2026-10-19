import pytest

from dbgpt_app.openapi.api_v1.dashboard.legacy_adapter import adapt_legacy_report


def _legacy_chart(index: int, chart_type: str):
    columns = ["total"] if chart_type == "IndicatorValue" else ["label", "total"]
    return {
        "chart_uid": f"legacy-{index}",
        "chart_name": f"Legacy {chart_type}",
        "chart_type": chart_type,
        "chart_desc": "Imported chart",
        "chart_sql": f"SELECT {index} AS total",
        "column_name": columns,
        "values": [],
    }


def test_import_maps_all_legacy_chart_types_and_preserves_context():
    report = {
        "conv_uid": "conversation-1",
        "template_name": "Legacy sales report",
        "template_introduce": "Existing dashboard payload",
        "charts": [
            _legacy_chart(1, "IndicatorValue"),
            _legacy_chart(2, "LineChart"),
            _legacy_chart(3, "BarChart"),
            _legacy_chart(4, "PieChart"),
            _legacy_chart(5, "Table"),
        ],
    }

    schema = adapt_legacy_report(report, "sales-db")

    assert [widget.type.value for widget in schema.widgets] == [
        "kpi",
        "line",
        "bar",
        "pie",
        "table",
    ]
    assert schema.metadata.conversation_id == "conversation-1"
    assert schema.dashboard.data_source_id == "sales-db"
    assert schema.widgets[1].query.sql == "SELECT 2 AS total"
    assert schema.metadata.compatibility["import_mode"] == "one_way_copy"


def test_unknown_legacy_chart_becomes_editable_table_and_ids_are_unique():
    first = _legacy_chart(1, "CustomChart")
    second = _legacy_chart(2, "CustomChart")
    second["chart_uid"] = first["chart_uid"]

    schema = adapt_legacy_report(
        {"template_name": "Legacy", "charts": [first, second]}, "db"
    )

    assert [widget.type.value for widget in schema.widgets] == ["table", "table"]
    assert len({widget.id for widget in schema.widgets}) == 2


@pytest.mark.parametrize("chart", [{"column_name": ["x"]}, {"chart_sql": "SELECT 1"}])
def test_incomplete_legacy_chart_is_rejected(chart):
    with pytest.raises(ValueError, match="requires chart_sql and column_name"):
        adapt_legacy_report({"template_name": "Broken", "charts": [chart]}, "db")
