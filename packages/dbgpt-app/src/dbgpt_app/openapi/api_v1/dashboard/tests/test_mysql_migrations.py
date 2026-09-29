import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

pytestmark = pytest.mark.mysql_integration


def _load_revision(filename: str):
    root = Path(__file__).parents[8]
    path = root / "pilot" / "meta_data" / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(module, connection, function_name: str):
    module.op = Operations(MigrationContext.configure(connection))
    getattr(module, function_name)()


def _drop_dashboard_tables(engine):
    with engine.begin() as connection:
        for table in (
            "dbgpt_dashboard_edit_version",
            "dbgpt_uploaded_dataset",
            "dbgpt_dashboard_annotation",
            "dbgpt_dashboard_share",
            "dbgpt_dashboard_operation",
            "dbgpt_serve_scheduled_run",
            "dbgpt_serve_scheduled_task",
            "dbgpt_dashboard_audit",
            "dbgpt_dashboard_member",
            "dbgpt_dashboard_revision",
            "dbgpt_dashboard",
        ):
            connection.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))


def test_committed_dashboard_migrations_on_mysql():
    database_url = os.getenv("DASHBOARD_TEST_MYSQL_URL")
    if not database_url:
        pytest.skip("DASHBOARD_TEST_MYSQL_URL is not configured")
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    baseline = _load_revision("20260811_0001_dashboard_v1_baseline.py")
    rbac = _load_revision("20260811_0002_dashboard_rbac_audit.py")
    schedules = _load_revision("20260811_0003_dashboard_schedules.py")
    collaboration = _load_revision("20260811_0004_dashboard_collaboration.py")
    shares = _load_revision("20260812_0005_dashboard_shares.py")
    task_assets = _load_revision("20260814_0006_dashboard_task_assets.py")
    annotations = _load_revision("20260816_0007_dashboard_annotations.py")
    latest_share = _load_revision("20260830_0008_dashboard_latest_public_link.py")
    annotation_intent = _load_revision("20260831_0009_dashboard_annotation_intent.py")
    upload_registry = _load_revision("20260831_0010_uploaded_dataset_registry.py")
    edit_versions = _load_revision("20260831_0011_dashboard_edit_versions.py")
    _drop_dashboard_tables(engine)
    try:
        with engine.begin() as connection:
            _run(baseline, connection, "upgrade")
            connection.execute(
                sa.text(
                    """
                    INSERT INTO dbgpt_dashboard
                        (id, owner_id, title, description, data_source_id,
                         schema_json, current_revision, status,
                         gmt_created, gmt_modified)
                    VALUES
                        ('mysql-dashboard', 'alice', 'MySQL migration', '',
                         'sales', '{}', 1, 'draft', CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP)
                    """
                )
            )
            _run(rbac, connection, "upgrade")
            _run(schedules, connection, "upgrade")
            _run(collaboration, connection, "upgrade")
            _run(shares, connection, "upgrade")
            _run(task_assets, connection, "upgrade")
            _run(annotations, connection, "upgrade")
            _run(latest_share, connection, "upgrade")
            _run(annotation_intent, connection, "upgrade")
            _run(upload_registry, connection, "upgrade")
            _run(edit_versions, connection, "upgrade")

            inspector = sa.inspect(connection)
            assert {
                "dbgpt_dashboard",
                "dbgpt_dashboard_revision",
                "dbgpt_dashboard_member",
                "dbgpt_dashboard_audit",
                "dbgpt_serve_scheduled_task",
                "dbgpt_serve_scheduled_run",
                "dbgpt_dashboard_operation",
                "dbgpt_dashboard_share",
                "dbgpt_dashboard_annotation",
                "dbgpt_uploaded_dataset",
                "dbgpt_dashboard_edit_version",
            } <= set(inspector.get_table_names())
            edit_version = connection.execute(
                sa.text(
                    "SELECT revision, source, actor_id "
                    "FROM dbgpt_dashboard_edit_version "
                    "WHERE dashboard_id = 'mysql-dashboard'"
                )
            ).one()
            assert tuple(edit_version) == (1, "migration", "alice")
            task_columns = {
                column["name"]
                for column in inspector.get_columns("dbgpt_serve_scheduled_task")
            }
            assert {
                "owner_id",
                "resource_type",
                "resource_id",
                "lease_owner",
                "lease_expires_at",
            } <= task_columns
            dashboard_columns = {
                column["name"] for column in inspector.get_columns("dbgpt_dashboard")
            }
            annotation_columns = {
                column["name"]
                for column in inspector.get_columns("dbgpt_dashboard_annotation")
            }
            assert "public_slug" in dashboard_columns
            assert "intent" in annotation_columns
            owner = connection.execute(
                sa.text(
                    "SELECT principal_id, role FROM dbgpt_dashboard_member "
                    "WHERE dashboard_id = 'mysql-dashboard'"
                )
            ).one()
            assert tuple(owner) == ("alice", "owner")
    finally:
        _drop_dashboard_tables(engine)
        engine.dispose()
