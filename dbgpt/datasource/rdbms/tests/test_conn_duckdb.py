"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_duckdb.py
"""

import tempfile

import pytest

from dbgpt.datasource.rdbms.conn_duckdb import DuckDbConnector


@pytest.fixture
def db():
    temp_db_file = tempfile.NamedTemporaryFile(delete=False)
    temp_db_file.close()
    conn = DuckDbConnector.from_file_path(temp_db_file.name + "duckdb.db")
    yield conn


def test_get_users(db):
    assert db.get_users() == []


def test_get_table_names(db):
    assert list(db.get_table_names()) == []


def test_get_charset(db):
    assert db.get_charset() == "UTF-8"


def test_get_table_comments(db):
    assert db.get_table_comments("test") == []


def test_table_simple_info(db):
    assert db.table_simple_info() == []


def test_execute(db):
    assert list(db.run("SELECT 42")[0]) == ["42"]
