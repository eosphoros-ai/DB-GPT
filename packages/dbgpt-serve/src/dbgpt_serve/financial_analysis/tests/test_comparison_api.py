from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dbgpt_serve.financial_analysis.api import CreateExport, CreateRun, make_router
from dbgpt_serve.session_file.api.endpoints import get_authenticated_owner

from .conftest import wait_ready
from .fixtures import report_config


def test_request_dispatch_preserves_single_file_defaults():
    assert CreateRun(session_id="s", file_ids=["a"]).mode == "report"
    for params in [
        {"file_ids": ["a", "b"]},
        {"mode": "comparison", "file_ids": ["a"]},
        {"mode": "comparison", "file_ids": ["a", "a"], "comparison": {"kind": "peer"}},
    ]:
        with pytest.raises(ValidationError):
            CreateRun(session_id="s", **params)


def test_export_language_contract_defaults_and_rejects_markup():
    request = {"session_id": "scope", "revision": "saved", "format": "html"}
    assert CreateExport(**request).language == "zh"
    assert CreateExport(**request, language="en").language == "en"
    with pytest.raises(ValidationError):
        CreateExport(**request, language='en"><script>')


def test_api_scope_versions_and_source_members(isolated_service):
    service, _, _, _ = isolated_service
    app = FastAPI()

    def owner(request: Request):
        return request.headers["user-id"]

    app.dependency_overrides[get_authenticated_owner] = owner
    app.include_router(make_router(service), prefix="/financial")
    with TestClient(app) as client:
        run_id = str(uuid4())
        response = client.post(
            "/financial/runs",
            headers={"user-id": "alice"},
            json={
                "session_id": "scope",
                "request_id": run_id,
                "mode": "comparison",
                "file_ids": ["a", "b"],
                "comparison": report_config(),
            },
        )
        assert response.status_code == 202
        wait_ready(service, run_id)
        url = f"/financial/runs/{run_id}/report?session_id=scope"
        report = client.get(url, headers={"user-id": "alice"}).json()["data"]
        assert report["mode"] == "comparison"
        assert (
            client.get(
                url + "&revision=" + report["revision"], headers={"user-id": "alice"}
            ).json()["data"]
            == report
        )
        assert client.get(url, headers={"user-id": "bob"}).status_code == 404
        assert (
            client.get(
                url.replace("scope", "other"), headers={"user-id": "alice"}
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/financial/runs/{run_id}/documents/nonmember/download?session_id=scope",
                headers={"user-id": "alice"},
            ).status_code
            == 404
        )
