"""Connector cache must follow the datasource registry.

A cached connector must not outlive a delete, edit or same-name
re-registration made through ConnectorManager's own methods.
"""

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from dbgpt.storage.metadata.db_manager import DatabaseManager
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector  # noqa: F401
from dbgpt_serve.datasource.manages.connect_config_db import (
    ConnectConfigDao,
    ConnectConfigEntity,
)
from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager
from dbgpt_serve.datasource.manages.db_conn_info import DBConfig


def _make_db(path, marker):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sales(secret TEXT)")
    conn.execute("INSERT INTO sales VALUES (?)", (marker,))
    conn.commit()
    conn.close()
    return str(path)


def _query(connector):
    with connector.session_scope() as session:
        return session.execute(text("SELECT secret FROM sales")).scalar()


@pytest.fixture()
def env(tmp_path):
    dbm = DatabaseManager()
    dbm.init_db(f"sqlite:///{tmp_path}/meta.db")
    ConnectConfigEntity.__table__.create(dbm.engine)
    manager = ConnectorManager(MagicMock())
    manager.storage = ConnectConfigDao(db_manager=dbm)
    manager._db_summary_client = MagicMock()
    db_a = _make_db(tmp_path / "a.db", "A_MARKER")
    db_b = _make_db(tmp_path / "b.db", "B_MARKER")
    yield manager, db_a, db_b
    manager.clear_connector_cache()


def _sqlite(file_path):
    return DBConfig(db_type="sqlite", db_name="poc", file_path=file_path)


def test_delete_and_reregister_drop_cached_connector(env):
    manager, db_a, db_b = env
    manager.add_db(_sqlite(db_a))
    assert _query(manager.get_connector("poc")) == "A_MARKER"

    manager.delete_db("poc")
    with pytest.raises(ValueError, match="not found"):
        manager.get_connector("poc")

    manager.add_db(_sqlite(db_b))
    assert _query(manager.get_connector("poc")) == "B_MARKER"


def test_edit_drops_cached_connector(env):
    manager, db_a, db_b = env
    manager.add_db(_sqlite(db_a))
    assert _query(manager.get_connector("poc")) == "A_MARKER"

    manager.edit_db(_sqlite(db_b))
    assert _query(manager.get_connector("poc")) == "B_MARKER"


@pytest.mark.parametrize("mutation", ["delete", "edit"])
def test_build_racing_a_mutation_is_not_cached(env, mutation):
    manager, db_a, db_b = env
    manager.add_db(_sqlite(db_a))
    real_build = manager._build_connector

    def build_then_mutate(db_name):
        # The registry row is read, then the mutation commits and evicts
        # before this build gets to publish.
        connector = real_build(db_name)
        if mutation == "delete":
            manager.delete_db(db_name)
        else:
            manager.edit_db(_sqlite(db_b))
        return connector

    manager._build_connector = build_then_mutate
    assert _query(manager.get_connector("poc")) == "A_MARKER"
    manager._build_connector = real_build

    if mutation == "delete":
        with pytest.raises(ValueError, match="not found"):
            manager.get_connector("poc")
    else:
        assert _query(manager.get_connector("poc")) == "B_MARKER"


def test_refresh_invalidates_off_the_event_loop(env):
    manager, db_a, _ = env
    manager.add_db(_sqlite(db_a))
    cached = manager.get_connector("poc")
    events = []

    class RecordingExecutor(ThreadPoolExecutor):
        def submit(self, fn, *args, **kwargs):
            if fn is manager.db_summary_client.db_summary_embedding:
                events.append(("embed", None))
                return None
            return super().submit(fn, *args, **kwargs)

    real_dispose = manager._dispose_connector

    def recording_dispose(connector):
        events.append(("dispose", threading.get_ident()))
        real_dispose(connector)

    manager._dispose_connector = recording_dispose
    executor = RecordingExecutor(max_workers=1)
    manager.system_app.get_component.return_value.create.return_value = executor

    async def refresh():
        assert await manager.async_db_summary_embedding("poc", "sqlite")
        return threading.get_ident()

    try:
        loop_thread = asyncio.run(refresh())
    finally:
        executor.shutdown()

    # Evicted before the embedding job is queued, and not on the loop thread.
    assert [name for name, _ in events] == ["dispose", "embed"]
    assert events[0][1] != loop_thread
    assert manager.get_connector("poc") is not cached
