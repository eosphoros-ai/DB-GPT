"""Opt-in integration coverage against a real MySQL server.

Set ``DASHBOARD_TEST_MYSQL_URL`` to an isolated database before running this file.
The test owns and recreates the ``sales`` and dashboard tables in that database.
"""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardConflictError,
    DashboardDao,
    DashboardEditVersionEntity,
    DashboardEntity,
    DashboardRevisionEntity,
    DashboardShareEntity,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardCreateRequest,
    DashboardSchemaV1,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector
from dbgpt_serve.scheduled_task.dao.task_dao import ScheduledTaskDao
from dbgpt_serve.scheduled_task.models.scheduled_task_model import ScheduledTaskEntity

pytestmark = pytest.mark.mysql_integration


class _CountingConnector:
    """Expose the real connector while recording database query executions."""

    def __init__(self, connector: MySQLConnector) -> None:
        self._connector = connector
        self.query_count = 0

    def __getattr__(self, name):
        return getattr(self._connector, name)

    def query_ex(self, *args, **kwargs):
        self.query_count += 1
        return self._connector.query_ex(*args, **kwargs)


def _schema(database_name: str) -> DashboardSchemaV1:
    return DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.3",
            "dashboard": {
                "title": "MySQL sales integration",
                "description": "Real MySQL persistence and query coverage",
                "data_source_id": database_name,
            },
            "metric_context": {
                "grain": "sale",
                "data_freshness": "integration fixture",
                "source_notes": ["temporary local MySQL database"],
            },
            "filters": [
                {
                    "id": "sale-date",
                    "type": "date_range",
                    "label": "Sale date",
                    "field": "sale_date",
                    "default": ["2024-01-01", "2024-12-31"],
                }
            ],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "query": {
                        "data_source_id": database_name,
                        "sql": (
                            "SELECT SUM(amount) AS total_sales FROM sales "
                            "WHERE sale_date BETWEEN :start_date AND :end_date"
                        ),
                        "filter_parameters": {
                            "sale-date": {
                                "start_parameter": "start_date",
                                "end_parameter": "end_date",
                            }
                        },
                        "output_fields": [{"name": "total_sales", "type": "number"}],
                        "timeout_seconds": 5,
                        "max_rows": 10,
                    },
                    "publication": {
                        "query": {
                            "data_source_id": database_name,
                            "sql": (
                                "SELECT sale_date, amount FROM sales ORDER BY sale_date"
                            ),
                            "output_fields": [
                                {"name": "sale_date", "type": "date"},
                                {"name": "amount", "type": "number"},
                            ],
                            "timeout_seconds": 5,
                            "max_rows": 100,
                        },
                        "filter_fields": {"sale-date": "sale_date"},
                        "measures": [
                            {
                                "source_field": "amount",
                                "output_field": "total_sales",
                                "aggregation": "sum",
                            }
                        ],
                        "output_columns": ["total_sales"],
                        "max_output_rows": 1,
                    },
                    "encoding": {"value": "total_sales"},
                }
            ],
            "layouts": {
                "desktop": [
                    {
                        "widget_id": "total-sales",
                        "x": 0,
                        "y": 0,
                        "w": 4,
                        "h": 3,
                    }
                ]
            },
        }
    )


@pytest.fixture
def mysql_runtime():
    mysql_url = os.getenv("DASHBOARD_TEST_MYSQL_URL")
    if not mysql_url:
        pytest.skip("DASHBOARD_TEST_MYSQL_URL is not configured")

    database_name = make_url(mysql_url).database
    if not database_name:
        pytest.fail("DASHBOARD_TEST_MYSQL_URL must include an isolated database name")
    if "test" not in database_name.lower():
        pytest.fail("The disposable MySQL database name must contain 'test'")

    manager = DatabaseManager()
    manager.init_db(mysql_url, base=Model, engine_args={"pool_pre_ping": True})

    with manager.engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS dbgpt_serve_scheduled_task"))
        connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard_share"))
        connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard_revision"))
        connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard_edit_version"))
        connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard"))
        connection.execute(text("DROP TABLE IF EXISTS sales"))

    DashboardEntity.__table__.create(manager.engine)
    DashboardEditVersionEntity.__table__.create(manager.engine)
    DashboardRevisionEntity.__table__.create(manager.engine)
    DashboardShareEntity.__table__.create(manager.engine)
    ScheduledTaskEntity.__table__.create(manager.engine)
    with manager.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE sales ("
                "id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                "sale_date DATE NOT NULL, "
                "amount DECIMAL(12, 2) NOT NULL"
                ") ENGINE=InnoDB"
            )
        )
        connection.execute(
            text("INSERT INTO sales (sale_date, amount) VALUES (:sale_date, :amount)"),
            [
                {"sale_date": "2024-01-10", "amount": 100},
                {"sale_date": "2024-06-15", "amount": 200.5},
                {"sale_date": "2025-01-05", "amount": 300},
            ],
        )

    real_connector = MySQLConnector.from_uri(mysql_url)
    connector = _CountingConnector(real_connector)
    service = DashboardService(
        dao=DashboardDao(manager), connector_resolver=lambda _: connector
    )
    try:
        yield service, manager, connector, database_name
    finally:
        real_connector.close()
        with manager.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS dbgpt_serve_scheduled_task"))
            connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard_share"))
            connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard_revision"))
            connection.execute(text("DROP TABLE IF EXISTS dbgpt_dashboard"))
            connection.execute(text("DROP TABLE IF EXISTS sales"))
        manager.engine.dispose()


def test_mysql_crud_refresh_publish_and_public_snapshot(mysql_runtime):
    service, manager, connector, database_name = mysql_runtime
    owner_id = "mysql-integration-owner"
    schema = _schema(database_name)
    validation = service.validate_schema(schema, execute_queries=False)
    assert validation.valid, [
        {
            "path": issue.path,
            "code": issue.code,
            "message": issue.message,
        }
        for issue in validation.issues
    ]
    created = service.create_dashboard(DashboardCreateRequest(schema=schema), owner_id)

    assert created.current_revision == 1
    assert service.get_dashboard(created.id, owner_id).id == created.id
    assert [item.id for item in service.list_dashboards(owner_id)] == [created.id]

    changed = created.schema_payload.model_copy(deep=True)
    changed.dashboard.title = "Updated MySQL dashboard"
    saved = service.update_dashboard(created.id, changed, 1, owner_id)
    assert saved.current_revision == 2
    with pytest.raises(DashboardConflictError):
        service.update_dashboard(created.id, changed, 1, owner_id)

    filters = {"sale-date": ["2024-01-01", "2024-12-31"]}
    refreshed = service.refresh_dashboard(created.id, filters, owner_id)
    assert refreshed.widgets["total-sales"].rows == [[300.5]]

    published = service.publish_dashboard(created.id, 2, filters, owner_id)
    token_hash = hashlib.sha256(published.share_token.encode("utf-8")).hexdigest()
    revision = service.dao.get_published_by_token_hash(token_hash)
    assert revision is not None
    assert published.share_token not in revision.share_token_hash

    query_count_after_publish = connector.query_count
    public_before_change = service.get_public_snapshot(published.share_token)
    assert public_before_change.snapshot.widgets["total-sales"].rows == [[300.5]]
    assert connector.query_count == query_count_after_publish

    with manager.engine.begin() as connection:
        connection.execute(
            text("UPDATE sales SET amount = 999 WHERE sale_date = '2024-01-10'")
        )

    refreshed_after_change = service.refresh_dashboard(created.id, filters, owner_id)
    assert refreshed_after_change.widgets["total-sales"].rows == [[1199.5]]
    public_after_change = service.get_public_snapshot(published.share_token)
    assert public_after_change.snapshot.widgets["total-sales"].rows == [[300.5]]


def test_mysql_execution_lease_allows_only_one_concurrent_worker(mysql_runtime):
    _, manager, _, _ = mysql_runtime
    task_id = "dashboard-concurrent-refresh"
    ScheduledTaskDao(manager).create(
        {
            "task_id": task_id,
            "task_name": "Concurrent dashboard refresh",
            "task_type": "dashboard_refresh",
            "cron_expression": "0 2 * * *",
            "payload_json": '{"dashboard_id":"dashboard-1"}',
            "enabled": True,
            "owner_id": "alice",
            "resource_type": "dashboard",
            "resource_id": "dashboard-1",
        }
    )
    barrier = Barrier(2)

    def claim(worker_id: str) -> bool:
        barrier.wait(timeout=5)
        return ScheduledTaskDao(manager).try_acquire_lease(
            task_id, worker_id, ttl_seconds=120
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, ["worker-a", "worker-b"]))

    assert sorted(results) == [False, True]
