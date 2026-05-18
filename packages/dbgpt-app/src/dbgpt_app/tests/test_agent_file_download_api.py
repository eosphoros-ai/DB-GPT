import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute

from dbgpt_serve.utils.auth import get_user_from_headers


def _download_route(agentic_data_api):
    for route in agentic_data_api.router.routes:
        if isinstance(route, APIRoute) and route.path == "/v1/agent/files/download":
            return route
    raise AssertionError("download route not found")


def test_agent_file_download_route_requires_user_dependency():
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    route = _download_route(agentic_data_api)

    assert any(
        dependency.call is get_user_from_headers
        for dependency in route.dependant.dependencies
    )


@pytest.mark.asyncio
async def test_agent_file_download_rejects_project_root_file(tmp_path, monkeypatch):
    from dbgpt.configs import model_config
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    project_file = tmp_path / "docker-compose.yml"
    project_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(model_config, "ROOT_PATH", str(tmp_path))
    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path / "pilot"))

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.download_agent_file(str(project_file))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_agent_file_download_allows_pilot_tmp_file(tmp_path, monkeypatch):
    from dbgpt.configs import model_config
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    pilot_tmp = tmp_path / "pilot" / "tmp"
    pilot_tmp.mkdir(parents=True)
    generated_file = pilot_tmp / "result.txt"
    generated_file.write_text("ok\n", encoding="utf-8")
    monkeypatch.setattr(model_config, "ROOT_PATH", str(tmp_path / "project"))
    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path / "pilot"))

    response = await agentic_data_api.download_agent_file(str(generated_file))

    assert isinstance(response, FileResponse)
    assert response.path == str(generated_file)
