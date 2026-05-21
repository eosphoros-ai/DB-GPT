import os
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute

from dbgpt_serve.utils.auth import get_user_from_headers


def _is_under(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


@pytest.fixture()
def non_tmp_workspace():
    parent = next(
        (
            candidate.resolve()
            for candidate in (Path.cwd(), Path.home())
            if not _is_under(candidate.resolve(), Path("/tmp"))
        ),
        None,
    )
    if parent is None:
        pytest.skip("requires a temporary workspace outside /tmp")

    with tempfile.TemporaryDirectory(
        prefix="dbgpt-agent-download-", dir=str(parent)
    ) as temp_dir:
        workspace = Path(temp_dir).resolve()
        assert not _is_under(workspace, Path("/tmp"))
        yield workspace


def _download_route(agentic_data_api):
    for route in agentic_data_api.router.routes:
        if isinstance(route, APIRoute) and route.path == "/v1/agent/files/download":
            return route
    raise AssertionError("download route not found")


def test_agent_file_download_route_uses_existing_user_dependency():
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    route = _download_route(agentic_data_api)

    assert any(
        dependency.call is get_user_from_headers
        for dependency in route.dependant.dependencies
    )


def test_agent_file_download_keeps_default_mock_user_compatibility():
    user = get_user_from_headers(user_id=None)

    assert user.user_id == "001"
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_agent_file_download_rejects_project_root_file(
    non_tmp_workspace, monkeypatch
):
    from dbgpt.configs import model_config
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    project_file = non_tmp_workspace / "docker-compose.yml"
    project_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(model_config, "ROOT_PATH", str(non_tmp_workspace))
    monkeypatch.setattr(model_config, "PILOT_PATH", str(non_tmp_workspace / "pilot"))

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.download_agent_file(str(project_file))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_agent_file_download_allows_pilot_tmp_file(
    non_tmp_workspace, monkeypatch
):
    from dbgpt.configs import model_config
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    pilot_tmp = non_tmp_workspace / "pilot" / "tmp"
    pilot_tmp.mkdir(parents=True)
    generated_file = pilot_tmp / "result.txt"
    generated_file.write_text("ok\n", encoding="utf-8")
    monkeypatch.setattr(model_config, "ROOT_PATH", str(non_tmp_workspace / "project"))
    monkeypatch.setattr(model_config, "PILOT_PATH", str(non_tmp_workspace / "pilot"))

    response = await agentic_data_api.download_agent_file(str(generated_file))

    assert isinstance(response, FileResponse)
    assert response.path == str(generated_file)


@pytest.mark.asyncio
async def test_agent_file_download_rejects_relative_path():
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    with pytest.raises(HTTPException) as exc_info:
        await agentic_data_api.download_agent_file(os.path.join("tmp", "result.txt"))

    assert exc_info.value.status_code == 400
