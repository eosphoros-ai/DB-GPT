"""Unit tests for the openGauss connector."""

from dbgpt_ext.datasource.rdbms.conn_openGauss import (
    openGaussConnector,
    openGaussParameters,
)


def test_openGauss_parameters_db_url():
    params = openGaussParameters(
        host="localhost",
        port=5432,
        user="test_user",
        password="test_password",
        database="test_db",
    )

    assert params.db_url() == (
        "postgresql+psycopg2://test_user:test_password@localhost:5432/test_db"
    )


def test_openGauss_parameters_create_connector(monkeypatch):
    params = openGaussParameters(
        host="localhost",
        port=5432,
        user="test_user",
        password="test_password",
        database="test_db",
    )
    sentinel = object()

    def fake_from_parameters(cls, parameters):
        assert parameters is params
        return sentinel

    monkeypatch.setattr(
        openGaussConnector,
        "from_parameters",
        classmethod(fake_from_parameters),
    )

    assert params.create_connector() is sentinel


def test_openGauss_connector_from_parameters(monkeypatch):
    params = openGaussParameters(
        host="localhost",
        port=5432,
        user="test_user",
        password="test_password",
        database="test_db",
        schema="analytics",
    )
    captured = {}
    sentinel = object()

    def fake_from_uri_db(
        cls,
        host,
        port,
        user,
        pwd,
        db_name,
        engine_args=None,
        **kwargs,
    ):
        captured["host"] = host
        captured["port"] = port
        captured["user"] = user
        captured["pwd"] = pwd
        captured["db_name"] = db_name
        captured["engine_args"] = engine_args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(
        openGaussConnector,
        "from_uri_db",
        classmethod(fake_from_uri_db),
    )

    assert openGaussConnector.from_parameters(params) is sentinel
    assert captured == {
        "host": "localhost",
        "port": 5432,
        "user": "test_user",
        "pwd": "test_password",
        "db_name": "test_db",
        "engine_args": {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        },
        "kwargs": {"schema": "analytics"},
    }


def test_openGauss_connector_from_uri_db(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_from_uri(cls, database_uri, engine_args=None, **kwargs):
        captured["database_uri"] = database_uri
        captured["engine_args"] = engine_args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(openGaussConnector, "from_uri", classmethod(fake_from_uri))

    assert (
        openGaussConnector.from_uri_db(
            host="localhost",
            port=5432,
            user="test_user",
            pwd="test password",
            db_name="test_db",
            engine_args={"pool_size": 3},
            schema="analytics",
        )
        is sentinel
    )
    assert captured == {
        "database_uri": "postgresql+psycopg2://test_user:test+password@localhost:5432/test_db",
        "engine_args": {"pool_size": 3},
        "kwargs": {"schema": "analytics"},
    }
