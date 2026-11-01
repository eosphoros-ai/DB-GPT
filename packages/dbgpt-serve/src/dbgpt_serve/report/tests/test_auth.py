"""Report authentication must run before any owner-scoped storage operation."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt.component import SystemApp
from dbgpt_serve.report import serve as serve_module
from dbgpt_serve.report.api import endpoints
from dbgpt_serve.report.config import ServeConfig

PREFIX = "/api/v1/reports"
ROUTES = [
    (method, route.path)
    for route in endpoints.router.routes
    for method in sorted(route.methods)
]


@pytest.fixture
def report_app(monkeypatch):
    endpoints._reset_endpoints()
    app = FastAPI()
    system_app = SystemApp(app)
    service = MagicMock()
    service.list_runs.return_value = []
    monkeypatch.setattr(serve_module, "ReportDao", MagicMock())
    monkeypatch.setattr(serve_module, "ReportService", lambda dao: service)
    serve = serve_module.ReportServe(
        system_app, config=ServeConfig(api_keys="first-key, second-key")
    )
    serve.init_app(system_app)
    serve._db_manager = MagicMock()
    serve.before_start()
    with TestClient(app) as client:
        yield client, service
    endpoints._reset_endpoints()


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer wrong-key", "Basic first-key", "Bearer"],
)
def test_all_report_routes_reject_invalid_credentials(
    report_app, method, path, authorization
):
    client, service = report_app
    headers = {"user-id": "target-owner"}
    if authorization is not None:
        headers["Authorization"] = authorization
    path = path.format(
        report_id="known-report",
        run_id="known-run",
        artifact_id="known-artifact",
        observation_id="known-observation",
        block_id="known-block",
    )
    response = client.request(method, PREFIX + path, headers=headers, json={})
    assert response.status_code == 401, response.text
    assert response.json()["err_code"] == "invalid_api_key"
    assert not service.mock_calls


@pytest.mark.parametrize("key", ["first-key", "second-key"])
def test_configured_keys_allow_owner_scoped_requests(report_app, key):
    client, service = report_app
    response = client.get(
        PREFIX + "/known-report/runs",
        headers={"user-id": "alice", "Authorization": f"Bearer {key}"},
    )
    assert response.status_code == 200, response.text
    service.list_runs.assert_called_once_with(
        "alice", "known-report", limit=50, offset=0
    )


def test_no_configured_key_preserves_anonymous_mode(report_app):
    client, service = report_app
    endpoints.init_endpoints(MagicMock(), service, ServeConfig())
    response = client.get(PREFIX + "/known-report/runs")
    assert response.status_code == 200, response.text
    service.list_runs.assert_called_once_with("001", "known-report", limit=50, offset=0)


def test_shutdown_fails_closed(report_app):
    client, service = report_app
    endpoints._reset_endpoints()
    response = client.get(PREFIX + "/known-report/runs")
    assert response.status_code == 503
    assert not service.mock_calls
