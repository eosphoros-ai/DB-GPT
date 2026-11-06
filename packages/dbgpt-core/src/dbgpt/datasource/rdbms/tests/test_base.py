"""Tests for the lazy metadata reflection of ``RDBMSConnector``."""

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
    # A second call reuses the reflected tables.
    assert conn.get_table_info() == table_info
