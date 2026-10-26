"""Build deterministic, database-backed public snapshot fixtures for both demos.

The generated JSON is suitable for UI tests and an offline presentation. It is
not a replacement for the production publish API: production share pages still
read immutable snapshots stored by ``DashboardService``.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = ROOT / "examples" / "dashboard"
GENERATED_ROOT = DEMO_ROOT / "generated"
SNAPSHOT_ROOT = DEMO_ROOT / "snapshots"
FIXED_TIME = "2026-08-11T00:00:00Z"

for package in (
    "dbgpt-app",
    "dbgpt-client",
    "dbgpt-core",
    "dbgpt-ext",
    "dbgpt-sandbox",
    "dbgpt-serve",
):
    sys.path.insert(0, str(ROOT / "packages" / package / "src"))

from build_demo_databases import build_financial, build_walmart  # noqa: E402

from dbgpt_app.openapi.api_v1.dashboard.publication import (  # noqa: E402
    DashboardPublicationService,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (  # noqa: E402
    DashboardSchemaV1,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService  # noqa: E402


class SQLiteDemoConnector:
    """Small connector adapter that exercises the production query service."""

    db_type = "sqlite"

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)

    def close(self) -> None:
        self.connection.close()

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


def _model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value.dict(by_alias=True)


def build_public_snapshot(schema_path: Path, database_path: Path) -> dict:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    schema = DashboardSchemaV1.model_validate(payload)
    connector = SQLiteDemoConnector(database_path)
    try:
        service = DashboardService(
            dao=object(), connector_resolver=lambda _data_source_id: connector
        )
        widgets = {}
        for widget in schema.widgets:
            result = service.validate_widget_query(schema, widget.id, {})
            result_payload = _model_dump(result)
            if result_payload.get("error"):
                raise RuntimeError(
                    f"Demo widget {widget.id} failed: {result_payload['error']}"
                )
            result_payload["duration_ms"] = 0
            result_payload["refreshed_at"] = FIXED_TIME
            widgets[widget.id] = result_payload
        publication_datasets = {}
        materialized = DashboardPublicationService().materialize(
            schema, service.query_executor
        )
        for widget_id, result in materialized.items():
            result_payload = _model_dump(result)
            result_payload["duration_ms"] = 0
            result_payload["refreshed_at"] = FIXED_TIME
            publication_datasets[widget_id] = result_payload
    finally:
        connector.close()

    snapshot = {
        "dashboard_id": schema.dashboard.id,
        "refreshed_at": FIXED_TIME,
        "filters": {item.id: item.default for item in schema.filters},
        "widgets": widgets,
        "publication_datasets": publication_datasets,
    }
    return {
        "dashboard_id": schema.dashboard.id,
        "published_revision": 1,
        "schema": _model_dump(schema),
        "snapshot": snapshot,
        "published_at": FIXED_TIME,
    }


def main() -> None:
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    cases = (
        (
            "walmart-sales",
            DEMO_ROOT / "schemas" / "walmart-sales.schema.json",
            GENERATED_ROOT / "walmart_sales_demo.db",
            build_walmart,
        ),
        (
            "apple-financial",
            DEMO_ROOT / "schemas" / "apple-financial.schema.json",
            GENERATED_ROOT / "apple_financial_demo.db",
            build_financial,
        ),
    )
    for name, schema_path, database_path, database_builder in cases:
        database_builder(database_path)
        public_snapshot = build_public_snapshot(schema_path, database_path)
        output_path = SNAPSHOT_ROOT / f"{name}.public.json"
        output_path.write_text(
            json.dumps(public_snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
