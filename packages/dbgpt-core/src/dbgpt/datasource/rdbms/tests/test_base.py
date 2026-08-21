import pytest
from sqlalchemy.exc import CompileError

from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.datasource.rdbms import base as rdbms_base
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters


class _Connection:
    def __init__(self, execute_error=None):
        self.execute_error = execute_error
        self.executed_statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def execute(self, statement):
        if self.execute_error:
            raise self.execute_error
        self.executed_statements.append(statement)


class _Engine:
    def __init__(self, connect_error=None, execute_error=None):
        self.connect_error = connect_error
        self.connected = False
        self.disposed = False
        self.connection = _Connection(execute_error)

    def connect(self):
        if self.connect_error:
            raise self.connect_error
        self.connected = True
        return self.connection

    def dispose(self):
        self.disposed = True


def _parameters() -> RDBMSDatasourceParameters:
    return RDBMSDatasourceParameters(
        host="localhost",
        port=9030,
        user="root",
        database="test",
        driver="starrocks",
        password="secret",
    )


def test_rdbms_connection_probe_does_not_create_connector(monkeypatch):
    engine = _Engine()
    monkeypatch.setattr(rdbms_base, "create_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(
        RDBMSDatasourceParameters,
        "create_connector",
        lambda self: pytest.fail("connection probing must not create a connector"),
    )

    assert _parameters().test_connection() is True
    assert engine.connected is True
    assert len(engine.connection.executed_statements) == 1
    assert str(engine.connection.executed_statements[0]).startswith("SELECT ")
    assert engine.disposed is True


def test_rdbms_connection_probe_disposes_engine_after_failure(monkeypatch):
    engine = _Engine(connect_error=RuntimeError("access denied"))
    monkeypatch.setattr(rdbms_base, "create_engine", lambda *args, **kwargs: engine)

    with pytest.raises(RuntimeError, match="access denied"):
        _parameters().test_connection()

    assert engine.disposed is True


def test_rdbms_connection_probe_disposes_engine_after_query_failure(monkeypatch):
    engine = _Engine(execute_error=RuntimeError("query denied"))
    monkeypatch.setattr(rdbms_base, "create_engine", lambda *args, **kwargs: engine)

    with pytest.raises(RuntimeError, match="query denied"):
        _parameters().test_connection()

    assert engine.disposed is True


def test_get_table_info_no_throw_handles_compile_errors(monkeypatch):
    connector = object.__new__(RDBMSConnector)
    connector._is_closed = True
    monkeypatch.setattr(
        connector,
        "get_table_info",
        lambda table_names=None: (_ for _ in ()).throw(
            CompileError("VARCHAR requires a length")
        ),
    )

    assert connector.get_table_info_no_throw() == ("Error: VARCHAR requires a length")


def test_default_connection_probe_closes_temporary_connector():
    class _Connector:
        closed = False

        def close(self):
            self.closed = True

    class _Parameters:
        def __init__(self):
            self.connector = _Connector()

        def create_connector(self):
            return self.connector

    parameters = _Parameters()

    assert BaseDatasourceParameters.test_connection(parameters) is True
    assert parameters.connector.closed is True
