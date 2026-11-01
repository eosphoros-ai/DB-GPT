import json
import runpy
import sqlite3
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.dashboard.publication import (
    DashboardPublicationService,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardSchemaV1,
    DashboardSnapshot,
    collect_schema_issues,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService


def _repository_root() -> Path:
    return next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / ".git").exists()
    )


class SQLiteDemoConnector:
    db_type = "sqlite"

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)

    def get_table_names(self):
        return [
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]

    def get_fields(self, table, database=None):
        return [
            (row[1], row[2])
            for row in self.connection.execute(f"PRAGMA table_info({table})")
        ]

    def query_ex(self, sql, params=None, timeout=None):
        cursor = self.connection.execute(sql, params or {})
        return [item[0] for item in cursor.description], cursor.fetchall()


@pytest.mark.parametrize(
    ("schema_name", "database_name", "builder_name"),
    [
        ("walmart-sales.schema.json", "walmart.db", "build_walmart"),
        ("apple-financial.schema.json", "financial.db", "build_financial"),
    ],
)
def test_demo_schema_executes_every_widget(
    tmp_path, schema_name, database_name, builder_name
):
    demo_root = _repository_root() / "examples" / "dashboard"
    builders = runpy.run_path(str(demo_root / "build_demo_databases.py"))
    database_path = tmp_path / database_name
    builders[builder_name](database_path)

    payload = json.loads(
        (demo_root / "schemas" / schema_name).read_text(encoding="utf-8")
    )
    schema = DashboardSchemaV1.model_validate(payload)
    connector = SQLiteDemoConnector(database_path)
    service = DashboardService(dao=object(), connector_resolver=lambda _: connector)

    result = service.validate_schema(schema, execute_queries=True)

    assert result.valid, [issue.model_dump() for issue in result.issues]
    assert set(result.widget_status.values()) == {"executed"}


def test_financial_demo_embeds_traceable_sec_source_metadata(tmp_path):
    demo_root = _repository_root() / "examples" / "dashboard"
    builders = runpy.run_path(str(demo_root / "build_demo_databases.py"))
    database_path = tmp_path / "financial.db"
    builders["build_financial"](database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT fiscal_year, filing_url, units FROM source_metadata "
            "ORDER BY fiscal_year"
        ).fetchall()

    assert [row[0] for row in rows] == [2022, 2023, 2024]
    assert all(row[1].startswith("https://www.sec.gov/") for row in rows)
    assert {row[2] for row in rows} == {"USD millions"}


def test_olist_demo_registration_is_anchored_to_the_current_checkout(tmp_path):
    from dbgpt_app.default_datasources import default_file_datasources

    checkout = tmp_path / "v3.8-checkout"
    pilot = checkout / "pilot"
    sources = {
        name: (paths, comment)
        for name, paths, comment in default_file_datasources(str(checkout), str(pilot))
    }

    paths, comment = sources["olist_ecommerce_demo"]
    assert paths == [
        str(
            checkout
            / "examples"
            / "dashboard"
            / "olist"
            / "data"
            / "generated"
            / "olist.db"
        )
    ]
    assert comment == "Olist 电商多表演示（完整八表 SQLite 数据集）"


def test_olist_demo_schema_has_complete_filter_and_publication_contract():
    demo_root = _repository_root() / "examples" / "dashboard"
    payload = json.loads(
        (demo_root / "schemas" / "olist-ecommerce.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema = DashboardSchemaV1.model_validate(payload)
    filter_ids = {item.id for item in schema.filters}

    assert collect_schema_issues(schema) == []
    assert schema.dashboard.data_source_id == "olist_ecommerce_demo"
    assert len(schema.widgets) == 6
    for widget in schema.widgets:
        assert set(widget.query.filter_parameters) == filter_ids
        assert widget.publication is not None
        assert set(widget.publication.filter_fields) == filter_ids
        assert widget.publication.query.max_rows > 0
        assert widget.publication.max_output_rows > 0


@pytest.mark.parametrize(
    ("snapshot_name", "first_filters", "second_filters", "widget_id"),
    [
        (
            "walmart-sales.public.json",
            {"stores": [1]},
            {"stores": [1, 2]},
            "total-sales",
        ),
        (
            "apple-financial.public.json",
            {"year": 2022},
            {"year": 2024},
            "annual-revenue",
        ),
    ],
)
def test_demo_public_snapshots_recalculate_from_frozen_filter_datasets(
    snapshot_name, first_filters, second_filters, widget_id
):
    snapshot_path = (
        _repository_root() / "examples" / "dashboard" / "snapshots" / snapshot_name
    )
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    schema = DashboardSchemaV1.model_validate(payload["schema"])
    snapshot = DashboardSnapshot.model_validate(payload["snapshot"])

    assert set(snapshot.publication_datasets) == {
        widget.id for widget in schema.widgets
    }
    service = DashboardPublicationService()
    first = service.filter_snapshot(schema, snapshot, first_filters)
    second = service.filter_snapshot(schema, snapshot, second_filters)

    assert first.unsupported_widget_ids == []
    assert second.unsupported_widget_ids == []
    assert (
        first.snapshot.widgets[widget_id].rows
        != second.snapshot.widgets[widget_id].rows
    )
