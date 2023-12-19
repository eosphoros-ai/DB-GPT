"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_doris.py
"""

import pytest
from dbgpt.datasource.rdbms.conn_doris import DorisConnect


@pytest.fixture
def db():
    conn = DorisConnect.from_uri_db("localhost", 9030, "root", "", "test")
    yield conn
