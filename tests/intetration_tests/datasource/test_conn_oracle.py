"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_oracle.py
    docker run -d -p 1521:1521 -e ORACLE_PASSWORD=oracle gvenzl/oracle-xe:21
    docker exec -it 7df26b427df0 /bin/bash
    sqlplus system/oracle
    Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.
    
    > create database test;
"""

import pytest

from dbgpt.datasource.rdbms.conn_oracle import OracleConnector

_create_table_sql = """
            CREATE TABLE test (
                id NUMBER(11) PRIMARY KEY
            )
            """


@pytest.fixture
def db():
    conn = OracleConnector.from_uri_db("localhost", 1521, "oracle", "oracle", "XE")
    yield conn


def test_get_usable_table_names(db):
    db.run(_create_table_sql)
    print(db._sync_tables_from_db())
    assert list(db.get_usable_table_names()) == ["TEST"]


def test_get_columns(db):
    print(db.get_columns("test"))


def test_get_table_info_with_table(db):
    # db.run(_create_table_sql)
    # print(db._sync_tables_from_db())
    print(db.get_table_info())


def test_get_current_db_name(db):
    print(db.get_current_db_name())
    assert db.get_current_db_name() == "ORACLE"


def test_table_simple_info(db):
    print(db.table_simple_info())


def test_get_table_names(db):
    print(db.get_table_names())


def test_get_sample_rows(db):
    print(db._get_sample_rows(db._metadata.tables["TEST"]))


def test_get_table_indexes(db):
    print(db._get_table_indexes(db._metadata.tables["TEST"]))


def test_run(db):
    SQL = "SELECT * FROM EMPLOYEES FETCH FIRST 50 ROWS ONLY"
    print(db.run(SQL))

def test_get_table_comment(db):
    print(db.get_table_comment("EMPLOYEES"))
    # print(db.get_table_comment("TEST"))

def test_get_fields(db):
    assert list(db.get_fields("test")[0])[0] == "id"


def test_get_users(db):
    print(db.get_users())


def test_get_charset(db):
    print(db.get_charset())


def test_get_collation(db):
    print(db.get_collation())
