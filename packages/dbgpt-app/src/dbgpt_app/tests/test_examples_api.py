import os
from pathlib import Path

import pytest
from fastapi import HTTPException

from dbgpt_serve.utils.auth import UserRequest


def _configure_example(tmp_path, monkeypatch, name: str):
    from dbgpt_app.openapi.api_v1 import examples_api

    source_path = tmp_path / "source.csv"
    source_path.write_text("value\n1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # The upload base directory falls back to CFG.SYSTEM_APP.work_dir when the
    # app is configured, which would bypass tmp_path and the guarded owner root.
    monkeypatch.setattr(examples_api.CFG, "SYSTEM_APP", None)
    monkeypatch.setitem(
        examples_api.EXAMPLE_FILES,
        "test_example",
        {
            "source_path": "source.csv",
            "builtin_path": "source.csv",
            "name": name,
        },
    )
    monkeypatch.setattr(
        examples_api, "_resolve_example_source", lambda _: str(source_path)
    )
    return examples_api


@pytest.mark.asyncio
async def test_use_example_file_rejects_traversal_name(tmp_path, monkeypatch):
    examples_api = _configure_example(tmp_path, monkeypatch, "../../outside.csv")

    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id="alice")
    )

    assert result.success is False
    assert not (tmp_path / "outside.csv").exists()


@pytest.mark.asyncio
async def test_use_example_file_rejects_absolute_name(tmp_path, monkeypatch):
    outside_path = tmp_path / "outside.csv"
    examples_api = _configure_example(tmp_path, monkeypatch, str(outside_path))

    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id="alice")
    )

    assert result.success is False
    assert not outside_path.exists()


@pytest.mark.asyncio
async def test_use_example_file_rejects_windows_path_separator(tmp_path, monkeypatch):
    examples_api = _configure_example(tmp_path, monkeypatch, r"..\outside.csv")

    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id="alice")
    )

    assert result.success is False
    assert not (tmp_path / "python_uploads" / "alice" / r"..\outside.csv").exists()


@pytest.mark.asyncio
async def test_use_example_file_accepts_plain_name(tmp_path, monkeypatch):
    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")

    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id="alice")
    )

    target_path = tmp_path / "python_uploads" / "alice" / "report.csv"
    assert result.success is True
    assert result.data == str(target_path)
    assert target_path.read_text(encoding="utf-8") == "value\n1\n"


@pytest.mark.parametrize("user_id", ["../../bob", "a/b", "..", r"..\bob", "bob/.."])
@pytest.mark.asyncio
async def test_use_example_file_rejects_traversal_user_id(
    tmp_path, monkeypatch, user_id
):
    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")

    with pytest.raises(HTTPException) as exc_info:
        await examples_api.use_example_file(
            "test_example", UserRequest(user_id=user_id)
        )

    assert exc_info.value.status_code == 400
    assert not (tmp_path / "python_uploads").exists()
    assert not (tmp_path.parent / "bob" / "report.csv").exists()


@pytest.mark.parametrize("user_id", [None, "", "   "])
@pytest.mark.asyncio
async def test_use_example_file_defaults_empty_user_id(tmp_path, monkeypatch, user_id):
    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")

    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id=user_id)
    )

    target_path = tmp_path / "python_uploads" / "default" / "report.csv"
    assert result.success is True
    assert result.data == target_path.as_posix()
    assert target_path.read_text(encoding="utf-8") == "value\n1\n"


@pytest.mark.asyncio
async def test_use_example_file_accepts_plain_user_id(tmp_path, monkeypatch):
    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")

    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id="user-1")
    )

    target_path = tmp_path / "python_uploads" / "user-1" / "report.csv"
    assert result.success is True
    assert result.data == target_path.as_posix()
    assert target_path.read_text(encoding="utf-8") == "value\n1\n"


@pytest.mark.asyncio
async def test_use_example_route_rejects_traversal_user_id(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")
    app = FastAPI()
    app.include_router(examples_api.router)
    app.dependency_overrides[examples_api.get_user_from_headers] = lambda: UserRequest(
        user_id="../../poc"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/examples/use", json={"example_id": "test_example"}
        )

    assert response.status_code == 400
    assert "Invalid user_id" in response.json()["detail"]
    assert not (tmp_path / "python_uploads").exists()
    assert not (tmp_path.parent / "poc" / "report.csv").exists()


@pytest.mark.asyncio
async def test_use_example_route_rejects_symlinked_owner_root(tmp_path, monkeypatch):
    """A symlinked owner root reaches the 400 mapping, not the 200 envelope.

    The traversal-user-id route test is rejected by ``_resolve_user_id`` and so
    never gets to the separate ``_resolve_upload_dir`` mapping. This one does.
    Creating a real directory symlink needs privileges that are not available
    everywhere, so only the ``os.path.islink`` predicate that the production
    check calls is narrowed to the owner root; the ValueError still comes out of
    ``python_upload_api._resolve_upload_dir`` itself.
    """
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")
    owner_root = tmp_path / "python_uploads" / "alice"

    real_islink = os.path.islink

    def islink(path):
        return True if Path(path) == owner_root else real_islink(path)

    monkeypatch.setattr(os.path, "islink", islink)

    app = FastAPI()
    app.include_router(examples_api.router)
    app.dependency_overrides[examples_api.get_user_from_headers] = lambda: UserRequest(
        user_id="alice"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/examples/use", json={"example_id": "test_example"}
        )

    assert response.status_code == 400, (
        f"symlinked owner root returned {response.status_code}: {response.text}"
    )
    assert "owner upload root must not be a symlink" in response.json()["detail"]
    assert not (owner_root / "report.csv").exists()
