"""Tests for the lazy metadata reflection of ``RDBMSConnector``."""

import threading

import pytest
from sqlalchemy import create_engine, text

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

    calls = []
    original_reflect = conn._metadata.reflect
    monkeypatch.setattr(
        conn._metadata,
        "reflect",
        lambda *args, **kwargs: calls.append(1) or original_reflect(*args, **kwargs),
    )
    assert conn.get_table_info() == table_info
    assert calls == []


def test_get_table_info_waits_for_reflection_in_other_thread(db_url, monkeypatch):
    conn = _PlainConnector.from_uri(db_url, sample_rows_in_table_info=0)
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
    # The second request must not read metadata while "a" is being reflected.
    second.join(0.3)
    assert second.is_alive()

    release.set()
    first.join(5)
    second.join(5)
    assert "CREATE TABLE a" in results["a"]
    assert "CREATE TABLE b" in results["b"]
    assert "CREATE TABLE b" not in results["a"]
