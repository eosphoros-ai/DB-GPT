# Imported pytest fixtures are injected as arguments below.
# ruff: noqa: F811
import json
import sqlite3
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.dashboard.catalog import preview_template
from dbgpt_app.openapi.api_v1.dashboard.catalog_ai import (
    TemplateAdaptRequest,
    adapt_template,
    create_adapted_template,
    template_features,
    validate_adapted_schema,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardSchemaV1

from .test_catalog_workspace import mapped_source  # noqa: F401
from .test_feedback import real_service  # noqa: F401


class Model:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []

    async def generate(self, request):
        self.calls.append(request)
        payload = next(self.payloads, None)
        assert payload is not None, request.messages[-1].content
        return SimpleNamespace(error_code=0, text=json.dumps(payload))


def plan(preview):
    return {
        "title": "已适配的交易看板",
        "description": "使用实际交易数据",
        "changes": ["将日期和金额映射到 purchased 与 net"],
        "widgets": preview["schema"]["widgets"],
        "filters": preview["schema"]["filters"],
    }


@pytest.mark.asyncio
async def test_repairs_invalid_sql_and_returns_real_results_without_creating(
    mapped_source,
):
    service, _, mapping = mapped_source
    preview = preview_template(
        service, "retail-overview", "renamed", "alice", mapping("retail-overview")
    )
    valid = plan(preview)
    broken = json.loads(json.dumps(valid))
    broken["widgets"][0]["query"]["sql"] = (
        "SELECT SUM(nonexistent_amount) AS value FROM transactions"
    )
    model = Model([broken, valid])
    before = service.list_dashboard_page("alice").total
    result = await adapt_template(
        service,
        "retail-overview",
        "alice",
        TemplateAdaptRequest(data_source_id="renamed", model="test"),
        model,
    )
    assert len(model.calls) == 2
    assert all(
        not item["error"] and item["rows"]
        for item in result["snapshot"]["widgets"].values()
    )
    assert result["schema"]["layouts"] == preview["schema"]["layouts"]
    assert service.list_dashboard_page("alice").total == before
    assert "purchased" in str(model.calls[0])
    assert "nonexistent_amount" in str(model.calls[1])


@pytest.mark.asyncio
async def test_ai_can_replace_an_unavailable_time_chart_with_real_categories(
    mapped_source,
):
    service, _, mapping = mapped_source
    original = preview_template(
        service, "retail-overview", "renamed", "alice", mapping("retail-overview")
    )
    adapted = plan(original)
    trend = next(item for item in adapted["widgets"] if item["id"] == "trend")
    trend.update(
        type="bar",
        title="按市场比较销售额",
        encoding={"x": "market", "y": "value"},
        publication={
            "query": {
                "data_source_id": "renamed",
                "sql": "SELECT market,net FROM transactions",
                "output_fields": [
                    {"name": "market", "type": "string"},
                    {"name": "net", "type": "number"},
                ],
            },
            "filter_fields": {},
            "group_by": ["market"],
            "measures": [
                {"source_field": "net", "output_field": "value", "aggregation": "sum"}
            ],
            "output_columns": ["market", "value"],
        },
    )
    trend["presentation"].update(visualization="column", unit="元")
    trend["query"].update(
        sql=(
            "SELECT market,SUM(net) AS value FROM transactions "
            "GROUP BY market ORDER BY value DESC"
        ),
        output_fields=[
            {"name": "market", "type": "string"},
            {"name": "value", "type": "number"},
        ],
        filter_parameters={},
        default_parameters={},
    )
    result = await adapt_template(
        service,
        "retail-overview",
        "alice",
        TemplateAdaptRequest(data_source_id="renamed", model="test"),
        Model([adapted]),
    )
    assert result["snapshot"]["widgets"]["trend"]["rows"] == [
        ["North", 85.0],
        ["South", 65.0],
    ]
    assert (
        next(item for item in result["schema"]["widgets"] if item["id"] == "trend")[
            "presentation"
        ]["visualization"]
        == "column"
    )


def test_creation_rejects_changed_source_or_layout(mapped_source):
    service, _, mapping = mapped_source
    preview = preview_template(
        service, "retail-overview", "renamed", "alice", mapping("retail-overview")
    )
    schema = DashboardSchemaV1.model_validate(preview["schema"])
    before = service.list_dashboard_page("alice").total
    schema.widgets[0].query.data_source_id = "not-selected"
    with pytest.raises(ValueError, match="数据源"):
        create_adapted_template(service, "retail-overview", "renamed", "alice", schema)
    assert service.list_dashboard_page("alice").total == before
    schema.widgets[0].query.data_source_id = "renamed"
    schema.layouts.desktop[0].w = 2
    with pytest.raises(ValueError, match="布局"):
        create_adapted_template(service, "retail-overview", "renamed", "alice", schema)
    assert service.list_dashboard_page("alice").total == before


@pytest.mark.asyncio
async def test_reference_positions_cannot_override_the_template_layout(mapped_source):
    service, _, mapping = mapped_source
    original = preview_template(
        service, "holiday-sales", "renamed", "alice", mapping("holiday-sales")
    )
    adapted = plan(original)
    for widget in adapted["widgets"]:
        widget["position"] = {"col": 0, "row": 0, "w": 12, "h": 20}
    model = Model([adapted])
    result = await adapt_template(
        service,
        "holiday-sales",
        "alice",
        TemplateAdaptRequest(data_source_id="renamed", model="test"),
        model,
    )
    assert len(model.calls) == 1
    assert result["schema"]["layouts"] == original["schema"]["layouts"]
    assert all("position" not in widget for widget in result["schema"]["widgets"])


@pytest.mark.asyncio
async def test_holiday_adaptation_preserves_all_33_months_and_series(mapped_source):
    service, path, mapping = mapped_source
    months = [f"{2023 + i // 12}-{i % 12 + 1:02d}" for i in range(33)]
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM transactions")
        conn.executemany(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?,?)",
            [
                (f"{i}-{market}", f"{month}-01", i + 1, market, "A", "a", 2)
                for i, month in enumerate(months)
                for market in ("North", "South")
            ],
        )
    original = preview_template(
        service, "holiday-sales", "renamed", "alice", mapping("holiday-sales")
    )
    model = Model([plan(original)])
    result = await adapt_template(
        service,
        "holiday-sales",
        "alice",
        TemplateAdaptRequest(data_source_id="renamed", model="test"),
        model,
    )
    trend = result["snapshot"]["widgets"]["trend"]
    assert len(model.calls) == 1
    assert len(trend["rows"]) == 66
    assert list(dict.fromkeys(row[0] for row in trend["rows"])) == months
    assert {row[1] for row in trend["rows"]} == {"North", "South"}
    assert not trend["truncated"]
    # Creating the exact preview revalidates it; long time axes must pass here too.
    record = create_adapted_template(
        service,
        "holiday-sales",
        "renamed",
        "alice",
        DashboardSchemaV1.model_validate(result["schema"]),
    )
    assert record.schema_payload.layouts.model_dump() == original["schema"]["layouts"]


@pytest.mark.parametrize("category_prefix", ["Store ", ""])
def test_dense_categories_still_require_a_bounded_ranking(
    mapped_source, category_prefix
):
    service, path, mapping = mapped_source
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM transactions")
        conn.executemany(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?,?)",
            [
                (
                    str(i),
                    "2025-01-01",
                    i + 1,
                    f"{category_prefix}{2000 + i}",
                    "A",
                    "a",
                    2,
                )
                for i in range(33)
            ],
        )
    preview = preview_template(
        service, "holiday-sales", "renamed", "alice", mapping("holiday-sales")
    )
    with pytest.raises(ValueError, match="33 个分类"):
        validate_adapted_schema(
            service,
            "holiday-sales",
            "renamed",
            "alice",
            DashboardSchemaV1.model_validate(preview["schema"]),
        )


def test_features_are_extracted_from_the_selected_composition():
    retail, revenue = (
        template_features("retail-overview"),
        template_features("northwind-revenue"),
    )
    assert retail["widgets"] != revenue["widgets"]
    assert retail["theme"] != revenue["theme"]
    assert "零售经营总览" in retail["prompt"]
