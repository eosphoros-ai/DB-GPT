"""Unit tests for the MSSQL connector parameters."""

import pytest

from dbgpt.datasource.rdbms import base as rdbms_base
from dbgpt_ext.datasource.rdbms.conn_mssql import MSSQLParameters


def test_mssql_parameters_bound_pymssql_connection_timeout():
    params = MSSQLParameters(
        host="localhost",
        port=1433,
        user="test_user",
        password="",
        database="test_db",
        connect_timeout=7,
    )

    assert params.engine_args()["connect_args"] == {
        "timeout": 7,
        "login_timeout": 7,
    }


def test_mssql_parameters_do_not_pass_pymssql_args_to_other_drivers():
    params = MSSQLParameters(
        host="localhost",
        port=1433,
        user="test_user",
        password="",
        database="test_db",
        driver="mssql+pyodbc",
    )

    assert "connect_args" not in params.engine_args()


def test_mssql_parameters_test_connection_uses_lightweight_probe(monkeypatch):
    calls = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            calls["connection_closed"] = True

        def execute(self, statement):
            calls["statement"] = str(statement)

    class FakeEngine:
        def connect(self):
            return FakeConnection()

        def dispose(self):
            calls["engine_disposed"] = True

    def fake_create_engine(url, **engine_args):
        calls["url"] = url
        calls["engine_args"] = engine_args
        return FakeEngine()

    monkeypatch.setattr(rdbms_base, "create_engine", fake_create_engine)

    params = MSSQLParameters(
        host="localhost",
        port=1433,
        user="test_user",
        password="",
        database="test_db",
        connect_timeout=7,
    )

    params.test_connection()

    assert calls["url"] == "mssql+pymssql://test_user:@localhost:1433/test_db"
    assert calls["engine_args"]["connect_args"] == {
        "timeout": 7,
        "login_timeout": 7,
    }
    assert calls["statement"] == "SELECT 1"
    assert calls["connection_closed"] is True
    assert calls["engine_disposed"] is True


def test_mssql_parameters_test_connection_cleans_up_after_probe_failure(monkeypatch):
    calls = {}

    class ProbeError(RuntimeError):
        pass

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            calls["connection_closed"] = True
            calls["connection_error_type"] = exc_type

        def execute(self, statement):
            raise ProbeError("probe failed")

    class FakeEngine:
        def connect(self):
            return FakeConnection()

        def dispose(self):
            calls["engine_disposed"] = True

    monkeypatch.setattr(
        rdbms_base,
        "create_engine",
        lambda url, **engine_args: FakeEngine(),
    )

    params = MSSQLParameters(
        host="localhost",
        port=1433,
        user="test_user",
        password="",
        database="test_db",
    )

    with pytest.raises(ProbeError, match="probe failed"):
        params.test_connection()

    assert calls["connection_closed"] is True
    assert calls["connection_error_type"] is ProbeError
    assert calls["engine_disposed"] is True
