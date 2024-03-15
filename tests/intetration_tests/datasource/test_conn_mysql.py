"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_mysql.py
    docker run -itd --name mysql-test -p 3307:3306 -e MYSQL_ROOT_PASSWORD=12345678 mysql:5.7
    mysql -h 127.0.0.1 -uroot -p -P3307
    Enter password:
    Welcome to the MySQL monitor.  Commands end with ; or \g.
    Your MySQL connection id is 2
    Server version: 5.7.41 MySQL Community Server (GPL)

    Copyright (c) 2000, 2023, Oracle and/or its affiliates.

    Oracle is a registered trademark of Oracle Corporation and/or its
    affiliates. Other names may be trademarks of their respective
    owners.

    Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.
    
    > create database test;
"""

import pytest

from dbgpt.datasource.rdbms.conn_mysql import MySQLConnect

_create_table_sql = """
            CREATE TABLE IF NOT EXISTS `test` (
                `id` int(11) DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """


@pytest.fixture
def db():
    conn = MySQLConnect.from_uri_db(
        "localhost",
        3307,
        "root",
        "********",
        "test",
        engine_args={"connect_args": {"charset": "utf8mb4"}},
    )
    yield conn


def test_get_usable_table_names(db):
    db.run(_create_table_sql)
    print(db._sync_tables_from_db())
    assert list(db.get_usable_table_names()) == []


def test_get_table_info(db):
    assert "CREATE TABLE test" in db.get_table_info()


def test_get_table_info_with_table(db):
    db.run(_create_table_sql)
    print(db._sync_tables_from_db())
    table_info = db.get_table_info()
    assert "CREATE TABLE test" in table_info


def test_run_no_throw(db):
    assert db.run_no_throw("this is a error sql").startswith("Error:")


def test_get_index_empty(db):
    db.run(_create_table_sql)
    assert db.get_indexes("test") == []


def test_get_fields(db):
    db.run(_create_table_sql)
    assert list(db.get_fields("test")[0])[0] == "id"


def test_get_charset(db):
    assert db.get_charset() == "utf8mb4" or db.get_charset() == "latin1"


def test_get_collation(db):
    assert (
        db.get_collation() == "utf8mb4_general_ci"
        or db.get_collation() == "latin1_swedish_ci"
    )


def test_get_users(db):
    assert ("root", "%") in db.get_users()


def test_get_database_lists(db):
    assert db.get_database_list() == ["test"]
