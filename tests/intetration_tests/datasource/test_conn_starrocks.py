"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_starrocks.py
    
    docker run -p 9030:9030 -p 8030:8030 -p 8040:8040 -itd --name quickstart starrocks/allin1-ubuntu
    
    mysql -P 9030 -h 127.0.0.1 -u root --prompt="StarRocks > "
    Welcome to the MySQL monitor.  Commands end with ; or \g.
    Your MySQL connection id is 184
    Server version: 5.1.0 3.1.5-5d8438a

    Copyright (c) 2000, 2023, Oracle and/or its affiliates.

    Oracle is a registered trademark of Oracle Corporation and/or its
    affiliates. Other names may be trademarks of their respective
    owners.

    Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

    > create database test;
"""

import pytest
from dbgpt.datasource.rdbms.conn_starrocks import StarRocksConnect


@pytest.fixture
def db():
    conn = StarRocksConnect.from_uri_db("localhost", 9030, "root", "", "test")
    yield conn


def test_get_table_names(db):
    assert list(db.get_table_names()) == []


def test_get_table_info(db):
    assert db.get_table_info() == ""


def test_get_table_info_with_table(db):
    db.run("create table test(id int)")
    print(db._sync_tables_from_db())
    table_info = db.get_table_info()
    assert "CREATE TABLE test" in table_info


def test_run_no_throw(db):
    assert db.run_no_throw("this is a error sql").startswith("Error:")


def test_get_index_empty(db):
    db.run("create table if not exists test(id int)")
    assert db.get_indexes("test") == []
