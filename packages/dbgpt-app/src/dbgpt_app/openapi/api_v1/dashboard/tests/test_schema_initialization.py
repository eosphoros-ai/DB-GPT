"""Exercise the existing SQLite startup path with real local Alembic history."""

import shutil
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

from dbgpt.storage.metadata import Model, db_manager
from dbgpt.util._db_migration_utils import _ddl_init_and_upgrade
from dbgpt_app.initialization.db_model_initialization import _MODELS  # noqa: F401

_ADDED_COLUMNS = {
    "dbgpt_serve_scheduled_task": {
        "owner_id",
        "resource_type",
        "resource_id",
        "lease_owner",
        "lease_expires_at",
    },
    "dbgpt_serve_scheduled_run": {
        "output_resource_id",
        "attempt_count",
        "result_json",
        "idempotency_key",
    },
    "chat_history_message": {"trace_id"},
}


def _is_dashboard(table):
    return (
        table.name.startswith("dbgpt_dashboard")
        or table.name == "dbgpt_uploaded_dataset"
    )


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    root = Path(__file__).parents[8]
    metadata_dir = tmp_path / "pilot/meta_data"
    scripts = metadata_dir / "alembic"
    scripts.mkdir(parents=True)
    shutil.copy2(root / "pilot/meta_data/alembic.ini", metadata_dir / "alembic.ini")
    for name in ("env.py", "script.py.mako"):
        shutil.copy2(root / "pilot/meta_data/alembic" / name, scripts / name)
    manager = db_manager.DatabaseManager()
    monkeypatch.setattr(db_manager, "db", manager)
    url = f"sqlite:///{metadata_dir / 'dbgpt.db'}"
    yield manager, url, metadata_dir
    if manager.engine is not None:
        manager.engine.dispose()


def _startup(manager, url, metadata_dir, base=Model):
    manager.init_db(url, base=base)
    manager.create_all()
    _ddl_init_and_upgrade(str(metadata_dir), disable_alembic_upgrade=False)


def test_fresh_database_uses_original_startup_and_creates_dashboard_tables(runtime):
    manager, url, metadata_dir = runtime
    _startup(manager, url, metadata_dir)
    expected = {
        table.name for table in Model.metadata.tables.values() if _is_dashboard(table)
    }
    assert len(expected) >= 13
    assert expected <= set(sa.inspect(manager.engine).get_table_names())
    with manager.engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    _startup(manager, url, metadata_dir)


def test_existing_database_keeps_its_generated_revision_and_task_data(runtime):
    manager, url, metadata_dir = runtime
    legacy = declarative_base()
    for table in Model.metadata.sorted_tables:
        if _is_dashboard(table):
            continue
        if table.name in _ADDED_COLUMNS:
            sa.Table(
                table.name,
                legacy.metadata,
                *[
                    column._copy()
                    for column in table.columns
                    if column.name not in _ADDED_COLUMNS[table.name]
                ],
            )
        else:
            table.to_metadata(legacy.metadata)
    _startup(manager, url, metadata_dir, legacy)
    revisions = set((metadata_dir / "alembic/versions").glob("*.py"))
    assert revisions
    with manager.engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO dbgpt_serve_scheduled_task "
                "(task_id, task_name, task_type, cron_expression, "
                "payload_json, enabled, user_name) "
                "VALUES ('existing', 'Existing task', 'chat_replay', "
                "'* * * * *', '{}', 1, 'Display name')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO dbgpt_serve_scheduled_run "
                "(run_id, task_id, started_at, status) "
                "VALUES ('old-run', 'existing', '2026-01-01 00:00:00', 'success')"
            )
        )
        old_revision = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    manager.engine.dispose()
    _startup(manager, url, metadata_dir)
    assert revisions <= set((metadata_dir / "alembic/versions").glob("*.py"))
    inspector = sa.inspect(manager.engine)
    assert "dbgpt_dashboard" in inspector.get_table_names()
    with manager.engine.connect() as connection:
        assert connection.execute(
            sa.text(
                "SELECT task_name, user_name, owner_id "
                "FROM dbgpt_serve_scheduled_task WHERE task_id='existing'"
            )
        ).one() == ("Existing task", "Display name", None)
        assert connection.execute(
            sa.text(
                "SELECT status, attempt_count FROM dbgpt_serve_scheduled_run "
                "WHERE run_id='old-run'"
            )
        ).one() == ("success", 1)
        assert (
            connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            != old_revision
        )
