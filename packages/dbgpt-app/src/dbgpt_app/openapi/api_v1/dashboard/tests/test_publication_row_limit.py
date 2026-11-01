"""The existing 5,000 bound must fail visibly, not silently publish 6,435 rows."""

import sqlite3

import pytest

from dbgpt_app.openapi.api_v1.dashboard.publication import (
    DashboardPublicationError,
    DashboardPublicationService,
)
from dbgpt_app.openapi.api_v1.dashboard.query_executor import DashboardQueryExecutor

from .test_publication import _materializable_schema


def test_6435_source_rows_keep_5000_bound_and_explicit_publication_failure():
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.execute(
        "CREATE TABLE sales (store INTEGER, sale_date TEXT, weekly_sales REAL)"
    )
    connection.executemany(
        "INSERT INTO sales VALUES (?, ?, ?)",
        [(i, "2024-01-05", 1.0) for i in range(6435)],
    )

    class Connector:
        db_type = "sqlite"

        def get_table_names(self):
            return ["sales"]

        def get_fields(self, table, database=None):
            return [
                ("store", "integer"),
                ("sale_date", "text"),
                ("weekly_sales", "real"),
            ]

        def query_ex(self, sql, params=None, timeout=None):
            result = connection.execute(sql, params or {})
            return [col[0] for col in result.description], result.fetchall()

    class RecordingExecutor(DashboardQueryExecutor):
        last_result = None

        def execute_widget(self, schema, widget_id, filters):
            self.last_result = super().execute_widget(schema, widget_id, filters)
            return self.last_result

    executor = RecordingExecutor(connector_resolver=lambda _: Connector())
    schema = _materializable_schema()
    for widget in schema.widgets:
        widget.publication.query.max_rows = 5000
    try:
        with pytest.raises(DashboardPublicationError, match="exceeded"):
            DashboardPublicationService().materialize(schema, executor)
        assert executor.last_result.error is None
        assert executor.last_result.row_count == 5000
        assert executor.last_result.truncated is True
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 6435
    finally:
        connection.close()
