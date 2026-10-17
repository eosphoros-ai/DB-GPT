"""Execute every Olist Dashboard widget through DB-GPT's real safety layer."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# This repository is frequently tested from a reused DB-GPT virtual environment.
# An editable install in that environment may still point at an older worktree,
# which would validate the example against stale Dashboard models.  Put every
# package ``src`` directory from *this* checkout first so this standalone
# verifier always exercises the code beside the example.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
for package_dir in sorted((REPOSITORY_ROOT / "packages").iterdir()):
    source_dir = package_dir / "src"
    if source_dir.is_dir():
        sys.path.insert(0, str(source_dir))

from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardSchemaV1,
    DashboardSnapshot,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT.parent / "schemas" / "olist-ecommerce.schema.json"


def _assert_same_widget(live, frozen, scenario: str) -> None:
    if live.error or frozen.error:
        raise AssertionError(
            f"{scenario}/{live.widget_id}: live={live.error}, frozen={frozen.error}"
        )
    if live.columns != frozen.columns or live.row_count != frozen.row_count:
        raise AssertionError(
            f"{scenario}/{live.widget_id}: result shape differs: "
            f"live={live.columns}/{live.row_count}, "
            f"frozen={frozen.columns}/{frozen.row_count}"
        )
    for row_index, (live_row, frozen_row) in enumerate(zip(live.rows, frozen.rows)):
        for column, live_value, frozen_value in zip(live.columns, live_row, frozen_row):
            if isinstance(live_value, (int, float)) and isinstance(
                frozen_value, (int, float)
            ):
                if not math.isclose(
                    float(live_value),
                    float(frozen_value),
                    rel_tol=1e-9,
                    abs_tol=0.1,
                ):
                    raise AssertionError(
                        f"{scenario}/{live.widget_id}[{row_index}].{column}: "
                        f"live={live_value}, frozen={frozen_value}"
                    )
            elif live_value != frozen_value:
                raise AssertionError(
                    f"{scenario}/{live.widget_id}[{row_index}].{column}: "
                    f"live={live_value!r}, frozen={frozen_value!r}"
                )


def verify(connector) -> None:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema = DashboardSchemaV1.model_validate(payload)
    service = DashboardService(dao=object(), connector_resolver=lambda _: connector)
    # Exercise the exact publication contract as well as the editor queries.
    # This catches a demo that renders locally but cannot produce a safe frozen
    # snapshot for anonymous share-page filtering.
    validation = service.validate_schema(
        schema,
        execute_queries=True,
        require_publication_bindings=True,
    )
    if not validation.valid:
        details = [issue.model_dump() for issue in validation.issues]
        raise AssertionError(json.dumps(details, ensure_ascii=False, indent=2))
    for widget in schema.widgets:
        status = validation.widget_status.get(widget.id)
        if status != "executed":
            raise AssertionError(f"Widget {widget.id} was not executed: {status}")
        print(f"PASS {widget.id:<22} executed through DashboardService")

    datasets = service.publication_service.materialize(schema, service.query_executor)
    published = DashboardSnapshot(
        dashboard_id=schema.dashboard.id,
        refreshed_at=datetime.now(),
        filters=service.query_executor.filter_values(schema, {}),
        widgets=service.query_executor.execute_dashboard(schema, {}),
        publication_datasets=datasets,
    )
    scenarios = {
        "defaults": {},
        "single": {
            "purchase-years": ["2018"],
            "customer-states": ["SP"],
            "order-status": "delivered",
        },
        "multiple": {
            "purchase-years": ["2017", "2018"],
            "customer-states": ["SP", "RJ"],
            "order-status": "all",
        },
        "cleared": {
            "purchase-years": [],
            "customer-states": [],
            "order-status": "all",
        },
    }
    for scenario, filters in scenarios.items():
        live = service.query_executor.execute_dashboard(schema, filters)
        frozen = service.publication_service.filter_snapshot(schema, published, filters)
        if frozen.unsupported_widget_ids:
            raise AssertionError(
                f"{scenario}: unsupported widgets {frozen.unsupported_widget_ids}"
            )
        for widget in schema.widgets:
            _assert_same_widget(
                live[widget.id], frozen.snapshot.widgets[widget.id], scenario
            )
        print(f"PASS share filters {scenario:<8} match live owner queries")
    print(f"Verified {len(schema.widgets)} publish-ready Olist Dashboard widgets")


def main() -> None:
    parser = argparse.ArgumentParser()
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--sqlite", type=Path)
    destination.add_argument("--mysql-url")
    args = parser.parse_args()

    if args.sqlite:
        connector = SQLiteConnector.from_file_path(str(args.sqlite.resolve()))
    else:
        connector = MySQLConnector.from_uri(args.mysql_url)
    try:
        verify(connector)
    finally:
        connector.close()


if __name__ == "__main__":
    main()
