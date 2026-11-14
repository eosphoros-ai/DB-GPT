"""Tests for the lazy metadata reflection of ``RDBMSConnector``."""

import threading

import pytest
from sqlalchemy import (
    BLANK_SCHEMA,
    Column,
    Integer,
    MetaData,
    Table,
    create_engine,
    event,
    text,
)

from dbgpt.datasource.rdbms.base import RDBMSConnector


class _PlainConnector(RDBMSConnector):
    """Keeps the base ``_sync_tables_from_db``, which does not reflect."""

    db_type = "sqlite"
    db_dialect = "sqlite"


def _execute(url, *statements):
    engine = create_engine(url)
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    engine.dispose()


def _count_reflect_calls(conn, monkeypatch):
    calls = []
    original_reflect = conn._metadata.reflect
    monkeypatch.setattr(
        conn._metadata,
        "reflect",
        lambda *args, **kwargs: calls.append(1) or original_reflect(*args, **kwargs),
    )
    return calls


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    _execute(
        url,
        "CREATE TABLE a (id INTEGER PRIMARY KEY, name TEXT)",
        "CREATE TABLE b (id INTEGER PRIMARY KEY, value REAL)",
    )
    return url


def test_init_does_not_reflect_schema(db_url):
    conn = _PlainConnector.from_uri(db_url)
    assert set(conn.get_table_names()) == {"a", "b"}
    assert conn._metadata.tables == {}


def test_get_table_info_reflects_only_requested_tables(db_url):
    conn = _PlainConnector.from_uri(db_url, sample_rows_in_table_info=0)
    table_info = conn.get_table_info(["a"])
    assert "CREATE TABLE a" in table_info
    assert "CREATE TABLE b" not in table_info
    assert set(conn._metadata.tables) == {"a"}


def test_get_table_info_all_tables(db_url):
    conn = _PlainConnector.from_uri(db_url, sample_rows_in_table_info=0)
    table_info = conn.get_table_info()
    assert "CREATE TABLE a" in table_info
    assert "CREATE TABLE b" in table_info


def test_get_table_info_reuses_reflected_tables(db_url, monkeypatch):
    conn = _PlainConnector.from_uri(db_url, sample_rows_in_table_info=0)
    table_info = conn.get_table_info()

    calls = _count_reflect_calls(conn, monkeypatch)
    assert conn.get_table_info() == table_info
    assert calls == []


class _ContentionTrackingLock:
    """Lock that records when an acquirer has to wait for another holder."""

    def __init__(self):
        self._lock = threading.Lock()
        self.contended = threading.Event()

    def __enter__(self):
        if not self._lock.acquire(blocking=False):
            self.contended.set()
            self._lock.acquire()
        return self

    def __exit__(self, *exc_info):
        self._lock.release()


def test_get_table_info_waits_for_reflection_in_other_thread(db_url, monkeypatch):
    conn = _PlainConnector.from_uri(db_url, sample_rows_in_table_info=0)
    lock = _ContentionTrackingLock()
    conn._metadata_lock = lock
    original_reflect = conn._metadata.reflect
    entered = threading.Event()
    release = threading.Event()

    def blocking_reflect(*args, **kwargs):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return original_reflect(*args, **kwargs)

    monkeypatch.setattr(conn._metadata, "reflect", blocking_reflect)
    results = {}

    def describe(name):
        results[name] = conn.get_table_info([name])

    first = threading.Thread(target=describe, args=("a",))
    first.start()
    assert entered.wait(5)
    second = threading.Thread(target=describe, args=("b",))
    second.start()
    # The second request reaches the lock while "a" is still being reflected
    # and has to wait instead of reading the metadata.
    assert lock.contended.wait(5)
    assert "b" not in results

    release.set()
    first.join(5)
    second.join(5)
    assert "CREATE TABLE a" in results["a"]
    assert "CREATE TABLE b" in results["b"]
    assert "CREATE TABLE b" not in results["a"]


def test_get_table_info_does_not_retry_views(db_url, monkeypatch):
    _execute(db_url, "CREATE VIEW v AS SELECT id FROM a")
    conn = _PlainConnector.from_uri(
        db_url, sample_rows_in_table_info=0, view_support=True
    )
    assert "v" in set(conn.get_table_names())
    table_info = conn.get_table_info()

    calls = _count_reflect_calls(conn, monkeypatch)
    assert conn.get_table_info() == table_info
    assert calls == []


def test_get_table_info_ignores_same_named_table_in_other_schema(db_url, tmp_path):
    other_url = f"sqlite:///{tmp_path / 'other.db'}"
    _execute(other_url, "CREATE TABLE a (id INTEGER PRIMARY KEY, secret TEXT)")
    engine = create_engine(db_url)

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection, _):
        dbapi_connection.execute(f"ATTACH DATABASE '{tmp_path / 'other.db'}' AS other")

    conn = _PlainConnector(engine, sample_rows_in_table_info=0)
    # A table of the same name reflected from another schema, as connectors
    # that reflect a configured schema up front leave behind.
    conn._metadata.reflect(bind=engine, schema="other", only=["a"])

    table_info = conn.get_table_info(["a"])
    assert "name TEXT" in table_info
    assert "secret" not in table_info


def test_get_table_info_uses_supplied_metadata_schema(db_url, monkeypatch):
    # Without a connector schema, ``MetaData.reflect`` falls back to the
    # supplied metadata's default schema, so tables are reflected there.
    conn = _PlainConnector(
        create_engine(db_url),
        metadata=MetaData(schema="main"),
        sample_rows_in_table_info=0,
    )
    table_info = conn.get_table_info(["a"])
    assert "name TEXT" in table_info
    assert "value REAL" not in table_info

    calls = _count_reflect_calls(conn, monkeypatch)
    assert conn.get_table_info(["a"]) == table_info
    assert calls == []


def test_get_table_info_reflects_default_schema_despite_schemaless_table(db_url):
    # A schema-less table supplied by the caller must not stop the table of
    # the same name in the metadata's default schema from being reflected.
    metadata = MetaData(schema="main")
    Table("a", metadata, Column("id", Integer, primary_key=True), schema=BLANK_SCHEMA)
    conn = _PlainConnector(
        create_engine(db_url),
        metadata=metadata,
        sample_rows_in_table_info=0,
    )
    table_info = conn.get_table_info(["a"])
    assert "name TEXT" in table_info
    assert "main.a" in conn._metadata.tables


def test_get_table_info_recovers_after_failed_reflection(db_url, monkeypatch):
    conn = _PlainConnector.from_uri(db_url, sample_rows_in_table_info=0)
    original_reflect = conn._metadata.reflect

    def failing_reflect(*args, only=None, **kwargs):
        # Load "a", then fail before "b" is reflected.
        original_reflect(*args, only=["a"], **kwargs)
        raise RuntimeError("connection lost")

    monkeypatch.setattr(conn._metadata, "reflect", failing_reflect)
    with pytest.raises(RuntimeError, match="connection lost"):
        conn.get_table_info()
    assert set(conn._metadata.tables) == {"a"}

    monkeypatch.setattr(conn._metadata, "reflect", original_reflect)
    table_info = conn.get_table_info()
    assert "CREATE TABLE a" in table_info
    assert "name TEXT" in table_info
    assert "CREATE TABLE b" in table_info
    assert "value REAL" in table_info


class _FallbackSchemaConnector(_PlainConnector):
    """Reflects a fallback schema up front, like the PostgreSQL connector."""

    def _reflection_schema(self):
        return self._schema or "main"

    def _sync_tables_from_db(self):
        self._metadata.reflect(bind=self._engine, schema=self._reflection_schema())
        return super()._sync_tables_from_db()


def test_get_table_info_reuses_tables_reflected_in_fallback_schema(db_url, monkeypatch):
    conn = _FallbackSchemaConnector.from_uri(db_url, sample_rows_in_table_info=0)
    assert set(conn._metadata.tables) == {"main.a", "main.b"}

    calls = _count_reflect_calls(conn, monkeypatch)
    table_info = conn.get_table_info(["a"])
    assert "name TEXT" in table_info
    assert calls == []
    # No schema-less duplicate is reflected next to the fallback-schema table.
    assert set(conn._metadata.tables) == {"main.a", "main.b"}
