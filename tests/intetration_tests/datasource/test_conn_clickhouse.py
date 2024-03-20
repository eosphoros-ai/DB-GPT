"""_Create_table
        CREATE TABLE default.my_first_table
        (
            `user_id` UInt32,
            `message` String,
            `timestamp` DateTime,
            `metric` Float32
        )
        ENGINE = MergeTree
        PRIMARY KEY (user_id, timestamp)
        ORDER BY (user_id, timestamp);
        
    # INSERT INTO my_first_table (user_id, message, timestamp, metric) VALUES
    (101, 'Hello, ClickHouse!',                                 now(),       -1.0    ),
    (102, 'Insert a lot of rows per batch',                     yesterday(), 1.41421 ),
    (102, 'Sort your data based on your commonly-used queries', today(),     2.718   ),
    (101, 'Granules are the smallest chunks of data read',      now() + 5,   3.14159 )
    """
from typing import Dict, List

import pytest

from dbgpt.datasource.rdbms.conn_clickhouse import ClickhouseConnector


@pytest.fixture
def db():
    conn = ClickhouseConnector.from_uri_db("localhost", 8123, "default", "", "default")
    yield conn


def test_create_table(db):
    _create_sql = """
        CREATE TABLE IF NOT EXISTS my_first_table
        (
            `user_id` UInt32,
            `message` String,
            `timestamp` DateTime,
            `metric` Float32
        )
        ENGINE = MergeTree
        PRIMARY KEY (user_id, timestamp)
        ORDER BY (user_id, timestamp);
    """
    db.run(_create_sql)
    assert list(db.get_table_names()) == ["my_first_table"]


def test_get_table_names(db):
    assert list(db.get_table_names()) == ["my_first_table"]


def test_get_indexes(db):
    assert [index.get("name") for index in db.get_indexes("my_first_table")][
        0
    ] == "primary_key"


def test_get_fields(db):
    assert list(db.get_fields("my_first_table")[0])[0][0] == "user_id"


def test_get_table_comments(db):
    assert db.get_table_comments("my_first_table") == []


def test_get_columns_comments(db):
    assert db.get_column_comments("default", "my_first_table")[0][1] == ""
