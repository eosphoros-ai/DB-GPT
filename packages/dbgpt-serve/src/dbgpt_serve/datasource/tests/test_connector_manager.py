from unittest.mock import MagicMock

import pytest

from dbgpt_serve.datasource.api.schemas import DatasourceCreateRequest
from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager


def test_connection_delegates_to_parameter_probe(monkeypatch):
    manager = object.__new__(ConnectorManager)
    parameters = MagicMock()
    parameters.test_connection.return_value = True
    monkeypatch.setattr(manager, "_create_parameters", lambda request: parameters)
    request = DatasourceCreateRequest(type="starrocks", params={})

    assert manager.test_connection(request) is True
    parameters.test_connection.assert_called_once_with()
    parameters.create_connector.assert_not_called()


def test_connection_preserves_authentication_failure(monkeypatch):
    manager = object.__new__(ConnectorManager)
    parameters = MagicMock()
    parameters.test_connection.side_effect = RuntimeError("1045 Access denied")
    monkeypatch.setattr(manager, "_create_parameters", lambda request: parameters)
    request = DatasourceCreateRequest(type="starrocks", params={})

    with pytest.raises(ValueError, match="1045 Access denied"):
        manager.test_connection(request)


def test_connection_reports_missing_password_environment_variable(monkeypatch):
    manager = object.__new__(ConnectorManager)
    create_parameters = MagicMock()
    monkeypatch.setattr(manager, "_create_parameters", create_parameters)
    monkeypatch.delenv("DBGPT_TEST_MISSING_PASSWORD", raising=False)
    request = DatasourceCreateRequest(
        type="starrocks",
        params={"password": "${env:DBGPT_TEST_MISSING_PASSWORD}"},
    )

    with pytest.raises(
        ValueError,
        match="Environment variable DBGPT_TEST_MISSING_PASSWORD not found",
    ):
        manager.test_connection(request)

    create_parameters.assert_not_called()
