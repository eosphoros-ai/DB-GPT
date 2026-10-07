from datetime import datetime
from decimal import Decimal

import pytest

from dbgpt_app.openapi.api_v1.dashboard.publication import (
    DashboardPublicationError,
    DashboardPublicationService,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardSchemaV1,
    DashboardSnapshot,
    WidgetQueryResult,
)


def _schema() -> DashboardSchemaV1:
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.3",
            "dashboard": {
                "id": "public-filter-demo",
                "title": "Public filter demo",
                "data_source_id": "demo",
            },
            "filters": [
                {
                    "id": "date",
                    "type": "date_range",
                    "label": "Date",
                    "field": "sale_date",
                    "default": ["2024-01-01", "2024-02-29"],
                },
                {
                    "id": "stores",
                    "type": "multi_select",
                    "label": "Stores",
                    "field": "store",
                    "default": [1, 2, 3],
                    "options": [
                        {"label": "Store 1", "value": 1},
                        {"label": "Store 2", "value": 2},
                        {"label": "Store 3", "value": 3},
                    ],
                },
            ],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT 1 AS total_sales",
                        "output_fields": [{"name": "total_sales", "type": "number"}],
                    },
                    "publication": {
                        "query": {
                            "data_source_id": "demo",
                            "sql": ("SELECT store, sale_date, weekly_sales FROM sales"),
                            "output_fields": [
                                {"name": "store", "type": "integer"},
                                {"name": "sale_date", "type": "date"},
                                {"name": "weekly_sales", "type": "number"},
                            ],
                            "max_rows": 100,
                        },
                        "filter_fields": {
                            "date": "sale_date",
                            "stores": "store",
                        },
                        "measures": [
                            {
                                "source_field": "weekly_sales",
                                "output_field": "total_sales",
                                "aggregation": "sum",
                            }
                        ],
                        "output_columns": ["total_sales"],
                        "max_output_rows": 1,
                    },
                    "encoding": {"value": "total_sales"},
                },
                {
                    "id": "sales-detail",
                    "type": "table",
                    "title": "Sales detail",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT store, sale_date, weekly_sales FROM sales",
                        "output_fields": [
                            {"name": "store", "type": "integer"},
                            {"name": "sale_date", "type": "date"},
                            {"name": "weekly_sales", "type": "number"},
                        ],
                    },
                    "publication": {
                        "query": {
                            "data_source_id": "demo",
                            "sql": ("SELECT store, sale_date, weekly_sales FROM sales"),
                            "output_fields": [
                                {"name": "store", "type": "integer"},
                                {"name": "sale_date", "type": "date"},
                                {"name": "weekly_sales", "type": "number"},
                            ],
                            "max_rows": 100,
                        },
                        "filter_fields": {
                            "date": "sale_date",
                            "stores": "store",
                        },
                        "output_columns": [
                            "store",
                            "sale_date",
                            "weekly_sales",
                        ],
                        "row_mode": True,
                        "sort": [
                            {"field": "sale_date", "direction": "descending"},
                            {"field": "store", "direction": "ascending"},
                        ],
                        "max_output_rows": 100,
                    },
                    "encoding": {"columns": ["store", "sale_date", "weekly_sales"]},
                },
                {
                    "id": "unsupported",
                    "type": "kpi",
                    "title": "Published value only",
                    "query": {
                        "data_source_id": "demo",
                        "sql": "SELECT 7 AS value",
                        "output_fields": [{"name": "value", "type": "number"}],
                    },
                    "encoding": {"value": "value"},
                },
            ],
            "layouts": {
                "desktop": [
                    {"widget_id": "total-sales", "x": 0, "y": 0, "w": 4, "h": 3},
                    {"widget_id": "sales-detail", "x": 0, "y": 3, "w": 8, "h": 5},
                    {"widget_id": "unsupported", "x": 8, "y": 0, "w": 4, "h": 3},
                ]
            },
        }
    )


def _dataset(widget_id: str, *, truncated: bool = False) -> WidgetQueryResult:
    return WidgetQueryResult(
        widget_id=widget_id,
        columns=["store", "sale_date", "weekly_sales"],
        rows=[
            [1, "2024-01-05", 100.0],
            [2, "2024-01-12", 50.0],
            [3, "2024-01-19", 25.0],
            [1, "2024-02-02", 30.0],
        ],
        row_count=4,
        truncated=truncated,
        refreshed_at=datetime(2024, 3, 1),
    )


def _materializable_schema() -> DashboardSchemaV1:
    schema = _schema().model_copy(deep=True)
    schema.widgets = [widget for widget in schema.widgets if widget.publication]
    return schema


class _PublicationExecutor:
    def __init__(self, *, truncated: bool = False):
        self.calls = []
        self.truncated = truncated

    def execute_widget(self, schema, widget_id, filters):
        self.calls.append((schema.dashboard.id, widget_id, filters))
        return _dataset(widget_id, truncated=self.truncated)


def _published_snapshot(datasets) -> DashboardSnapshot:
    return DashboardSnapshot(
        dashboard_id="public-filter-demo",
        refreshed_at=datetime(2024, 3, 1),
        filters={
            "date": ["2024-01-01", "2024-02-29"],
            "stores": [1, 2, 3],
        },
        widgets={
            "unsupported": WidgetQueryResult(
                widget_id="unsupported",
                columns=["value"],
                rows=[[7]],
                row_count=1,
                refreshed_at=datetime(2024, 3, 1),
            )
        },
        publication_datasets=datasets,
    )


def test_public_filters_use_only_frozen_rows_and_keep_unsupported_widgets():
    schema = _schema()
    executor = _PublicationExecutor()
    service = DashboardPublicationService()
    datasets = service.materialize(_materializable_schema(), executor)
    calls_after_publish = list(executor.calls)

    response = service.filter_snapshot(
        schema,
        _published_snapshot(datasets),
        {
            "date": ["2024-01-01", "2024-01-31"],
            "stores": [1, 2],
        },
    )

    assert executor.calls == calls_after_publish
    assert response.snapshot.widgets["total-sales"].rows == [[150]]
    assert response.snapshot.widgets["sales-detail"].rows == [
        [2, "2024-01-12", 50.0],
        [1, "2024-01-05", 100.0],
    ]
    assert response.snapshot.widgets["unsupported"].rows == [[7]]
    assert response.unsupported_widget_ids == ["unsupported"]
    assert response.snapshot.publication_datasets == {}


def test_empty_multi_select_means_all_values():
    schema = _schema()
    datasets = {
        "total-sales": _dataset("total-sales"),
        "sales-detail": _dataset("sales-detail"),
    }

    response = DashboardPublicationService().filter_snapshot(
        schema,
        _published_snapshot(datasets),
        {
            "date": ["2024-01-01", "2024-01-31"],
            "stores": [],
        },
    )

    assert response.snapshot.widgets["total-sales"].rows == [[175]]
    assert response.snapshot.widgets["sales-detail"].row_count == 3


def test_ratio_measure_uses_summed_numerator_and_denominator():
    payload = _schema().model_dump(mode="json")
    payload["widgets"] = [payload["widgets"][0]]
    widget = payload["widgets"][0]
    widget["query"]["output_fields"] = [{"name": "delivered_rate", "type": "number"}]
    widget["encoding"] = {"value": "delivered_rate"}
    widget["publication"]["query"]["output_fields"] = [
        {"name": "store", "type": "integer"},
        {"name": "sale_date", "type": "date"},
        {"name": "delivered_count", "type": "integer"},
        {"name": "order_count", "type": "integer"},
    ]
    widget["publication"]["measures"] = [
        {
            "source_field": "delivered_count",
            "denominator_field": "order_count",
            "output_field": "delivered_rate",
            "aggregation": "ratio",
            "scale": 100,
        }
    ]
    widget["publication"]["output_columns"] = ["delivered_rate"]
    schema = DashboardSchemaV1.model_validate(payload)
    dataset = WidgetQueryResult(
        widget_id="total-sales",
        columns=["store", "sale_date", "delivered_count", "order_count"],
        rows=[
            [1, "2024-01-05", 1, 10],
            [2, "2024-01-05", 9, 10],
        ],
        row_count=2,
        refreshed_at=datetime(2024, 3, 1),
    )
    snapshot = DashboardSnapshot(
        dashboard_id="public-filter-demo",
        refreshed_at=datetime(2024, 3, 1),
        filters={},
        widgets={},
        publication_datasets={"total-sales": dataset},
    )

    service = DashboardPublicationService()
    all_stores = service.filter_snapshot(schema, snapshot, {"stores": []})
    store_one = service.filter_snapshot(schema, snapshot, {"stores": [1]})

    assert all_stores.snapshot.widgets["total-sales"].rows == [[50]]
    assert store_one.snapshot.widgets["total-sales"].rows == [[10]]


def test_numeric_filter_values_match_database_decimals_without_matching_booleans():
    schema = _schema()
    dataset = _dataset("total-sales")
    dataset.rows[0][0] = Decimal("1")
    datasets = {
        "total-sales": dataset,
        "sales-detail": _dataset("sales-detail"),
    }

    response = DashboardPublicationService().filter_snapshot(
        schema,
        _published_snapshot(datasets),
        {"stores": [1]},
    )

    assert response.snapshot.widgets["total-sales"].rows == [[130]]


@pytest.mark.parametrize(
    "filters",
    [
        {"unknown": 1},
        {"date": ["2024-01-01"]},
        {"date": ["not-a-date", "2024-01-31"]},
        {"date": ["2024-02-01", "2024-01-01"]},
        {"stores": 1},
        {"stores": [99]},
        {"stores": [[1, 2]]},
    ],
)
def test_public_filters_reject_unknown_or_invalid_values(filters):
    with pytest.raises(DashboardPublicationError):
        DashboardPublicationService().filter_snapshot(
            _schema(), _published_snapshot({}), filters
        )


def test_truncated_publication_dataset_blocks_publish():
    with pytest.raises(DashboardPublicationError, match="exceeded"):
        DashboardPublicationService().materialize(
            _materializable_schema(), _PublicationExecutor(truncated=True)
        )


def test_filtered_schema_cannot_publish_with_silent_static_widgets():
    with pytest.raises(DashboardPublicationError, match="unsupported"):
        DashboardPublicationService().materialize(_schema(), _PublicationExecutor())


def test_explicit_static_snapshot_fallback_materializes_only_bound_widgets():
    schema = _schema()
    executor = _PublicationExecutor()

    datasets = DashboardPublicationService().materialize(
        schema,
        executor,
        allow_static_widgets=True,
    )

    assert set(datasets) == {"total-sales", "sales-detail"}
    assert {call[1] for call in executor.calls} == {
        "total-sales",
        "sales-detail",
    }


def test_text_and_number_range_filters_recalculate_from_frozen_rows():
    payload = _schema().model_dump(mode="json")
    payload["filters"].extend(
        [
            {
                "id": "store-name",
                "type": "text",
                "label": "Store name contains",
                "field": "store_name",
                "default": "",
            },
            {
                "id": "sales-range",
                "type": "number_range",
                "label": "Sales range",
                "field": "weekly_sales",
                "default": [],
            },
        ]
    )
    payload["widgets"] = [payload["widgets"][1]]
    payload["widgets"][0]["publication"]["filter_fields"].update(
        {
            "store-name": "store_name",
            "sales-range": "weekly_sales",
        }
    )
    payload["widgets"][0]["publication"]["query"]["output_fields"].append(
        {"name": "store_name", "type": "string"}
    )
    schema = DashboardSchemaV1.model_validate(payload)
    dataset = _dataset("sales-detail")
    dataset.columns.append("store_name")
    for row, name in zip(dataset.rows, ["North", "South", "North East", "West"]):
        row.append(name)

    response = DashboardPublicationService().filter_snapshot(
        schema,
        _published_snapshot({"sales-detail": dataset}),
        {
            "store-name": "north",
            "sales-range": [20, 90],
        },
    )

    assert response.snapshot.widgets["sales-detail"].rows == [[3, "2024-01-19", 25.0]]


@pytest.mark.parametrize("schema_version", ["1.0", "1.1", "1.2"])
def test_legacy_filtered_schema_cannot_publish_misleading_static_results(
    schema_version,
):
    schema = _schema().model_copy(deep=True)
    schema.schema_version = schema_version
    for widget in schema.widgets:
        widget.publication = None

    with pytest.raises(DashboardPublicationError, match="Missing bindings"):
        DashboardPublicationService().materialize(schema, _PublicationExecutor())


def test_publication_rejects_a_visible_filter_that_changes_no_widget():
    payload = _materializable_schema().model_dump(mode="json")
    payload["filters"].append(
        {
            "id": "empty-shell",
            "type": "multi_select",
            "label": "Unbound filter",
            "field": "unused",
            "default": [],
            "options": [],
        }
    )
    schema = DashboardSchemaV1.model_validate(payload)

    with pytest.raises(DashboardPublicationError, match="do not recalculate"):
        DashboardPublicationService().materialize(schema, _PublicationExecutor())
