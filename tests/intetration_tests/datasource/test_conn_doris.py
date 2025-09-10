"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_doris.py

    docker run -it -d --name doris -p 8030:8030 -p 8040:8040 -p 9030:9030 -p 8048:8048 apache/doris:doris-all-in-one-2.1.0

    9030: The MySQL protocol port of FE.

    Connection: mysql -uadmin -P9030 -h127.0.0.1

"""

import pytest

from dbgpt_ext.datasource.rdbms.conn_doris import DorisConnector

_create_table_sql = """
            CREATE TABLE IF NOT EXISTS `test` (
                `id` int(11) DEFAULT NULL,
                `name` VARCHAR(200) DEFAULT NULL,
                `sex` VARCHAR(200) DEFAULT NULL,
                INDEX idx_name (`name`) USING INVERTED
                ) UNIQUE KEY(`id`)
                DISTRIBUTED BY HASH(`id`) BUCKETS 10
                PROPERTIES (
                    "replication_allocation" = "tag.location.default: 1"
                );
            """


@pytest.fixture
def db():
    conn = DorisConnector.from_uri_db("localhost", 9030, "admin", "", "test")
    yield conn


def test_get_usable_table_names(db):
    db.run(_create_table_sql)
    print(db._sync_tables_from_db())
    assert list(db.get_usable_table_names()) == ['test']


def test_get_table_info(db):
    db.run(_create_table_sql)
    print(db._sync_tables_from_db())
    assert "CREATE TABLE test" in db.get_table_info()


def test_run_no_throw(db):
    assert db.run_no_throw("this is a error sql") == []


def test_get_index(db):
    db.run(_create_table_sql)
    assert db.get_indexes("test") == [('idx_name', 'name')]


def test_get_fields(db):
    db.run(_create_table_sql)
    assert list(db.get_fields("test")[0])[0] == "id"


def test_get_charset(db):
    assert db.get_charset() == "utf8mb4"


def test_get_collation(db):
    assert (
        db.get_collation() == "utf8mb4_0900_bin"
        or db.get_collation() == "utf8mb4_general_ci"
    )

def test_get_users(db):
    assert db.get_users() == []

def test_get_database_lists(db):
    assert "test" in db.get_database_names()
