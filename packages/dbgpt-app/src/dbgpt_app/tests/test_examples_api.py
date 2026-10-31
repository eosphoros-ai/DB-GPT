import pytest
from fastapi import HTTPException

from dbgpt_serve.utils.auth import UserRequest


def _configure_example(tmp_path, monkeypatch, name: str):
    from dbgpt_app.openapi.api_v1 import examples_api

    source_path = tmp_path / "source.csv"
    source_path.write_text("value\n1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
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
