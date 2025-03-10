"""
Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_sqlite.py
"""

import os
import tempfile

import pytest

from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector


@pytest.fixture
def db():
    temp_db_file = tempfile.NamedTemporaryFile(delete=False)
    temp_db_file.close()
    conn = SQLiteConnector.from_file_path(temp_db_file.name)
    yield conn
    try:
        # TODO: Failed on windows
        os.unlink(temp_db_file.name)
    except Exception as e:
        print(f"An error occurred: {e}")


def test_get_table_names(db):
    assert list(db.get_table_names()) == []


def test_get_table_info(db):
    assert db.get_table_info() == ""


def test_get_table_info_with_table(db):
    db.run("CREATE TABLE test (id INTEGER);")
    print(db._sync_tables_from_db())
    table_info = db.get_table_info()
    assert "CREATE TABLE test" in table_info


def test_run_sql(db):
    result = db.run("CREATE TABLE test(id INTEGER);")
    assert result[0] == ("id", "INTEGER", 0, None, 0)


def test_run_no_throw(db):
    assert db.run_no_throw("this is a error sql") == []


def test_get_indexes(db):
    db.run("CREATE TABLE test (name TEXT);")
    db.run("CREATE INDEX idx_name ON test(name);")
    indexes = db.get_indexes("test")
    assert indexes == [{"name": "idx_name", "column_names": ["name"]}]


def test_get_indexes_empty(db):
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    assert db.get_indexes("test") == []


def test_get_show_create_table(db):
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    assert (
        db.get_show_create_table("test") == "CREATE TABLE test (id INTEGER PRIMARY KEY)"
    )


def test_get_fields(db):
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    assert db.get_fields("test") == [("id", "INTEGER", 0, None, 1)]


def test_get_charset(db):
    assert db.get_charset() == "UTF-8"


def test_get_collation(db):
    assert db.get_collation() == "UTF-8"


def test_table_simple_info(db):
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    assert db.table_simple_info() == ["test(id);"]


def test_get_table_info_no_throw(db):
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    assert db.get_table_info_no_throw("xxxx_table").startswith("Error:")


def test_query_ex(db):
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    db.run("insert into test(id) values (1)")
    db.run("insert into test(id) values (2)")
    field_names, result = db.query_ex("select * from test")
    assert field_names == ["id"]
    assert result == [(1,), (2,)]

    field_names, result = db.query_ex("select * from test", fetch="one")
    assert field_names == ["id"]
    assert result == [1]


def test_convert_sql_write_to_select(db):
    # TODO
    pass


def test_get_grants(db):
    assert db.get_grants() == []


def test_get_users(db):
    assert db.get_users() == []


def test_get_table_comments(db):
    assert db.get_table_comments() == []
    db.run("CREATE TABLE test (id INTEGER PRIMARY KEY);")
    assert db.get_table_comments() == [
        ("test", "CREATE TABLE test (id INTEGER PRIMARY KEY)")
    ]


def test_get_database_names(db):
    db.get_database_names() == []


def test_db_dir_exist_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        new_dir = os.path.join(temp_dir, "new_dir")
        file_path = os.path.join(new_dir, "sqlite.db")
        db = SQLiteConnector.from_file_path(file_path)
        assert os.path.exists(new_dir) is True
        assert list(db.get_table_names()) == []
    with tempfile.TemporaryDirectory() as existing_dir:
        file_path = os.path.join(existing_dir, "sqlite.db")
        db = SQLiteConnector.from_file_path(file_path)
        assert os.path.exists(existing_dir) is True
        assert list(db.get_table_names()) == []
