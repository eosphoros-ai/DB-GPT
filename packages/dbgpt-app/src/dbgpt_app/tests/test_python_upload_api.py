from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from dbgpt_serve.utils.auth import UserRequest


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content_type = "text/x-python"
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.mark.asyncio
async def test_python_file_upload_rejects_traversal_filename(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("../../outside.py", b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "outside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_absolute_filename(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile(str(tmp_path / "outside.py"), b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "outside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_allows_plain_filename_inside_user_dir(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b"print('inside')"),
        UserRequest(user_id="alice"),
    )

    expected_path = tmp_path / "python_uploads" / "alice" / "inside.py"
    assert result.success is True
    assert result.data == str(expected_path)
    assert expected_path.read_bytes() == b"print('inside')"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlink_escape(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    outside_dir = tmp_path / "outside"
    upload_dir.mkdir(parents=True)
    outside_dir.mkdir()
    try:
        (upload_dir / "linked").symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("linked/escaped.py", b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (outside_dir / "escaped.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_traversal_user_id(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_dir.mkdir()

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('inside')"),
            UserRequest(user_id=f"../../{outside_dir.name}"),
        )

    assert exc_info.value.status_code == 400
    assert not (outside_dir / "inside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_whitespace_user_id(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('inside')"),
            UserRequest(user_id=" alice "),
        )

    assert exc_info.value.status_code == 400
    assert not (tmp_path / "python_uploads" / " alice ").exists()


@pytest.mark.parametrize("user_id", [None, "", "   "])
@pytest.mark.asyncio
async def test_python_file_upload_defaults_empty_user_id(
    tmp_path, monkeypatch, user_id
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b"print('inside')"),
        UserRequest(user_id=user_id),
    )

    expected_path = tmp_path / "python_uploads" / "default" / "inside.py"
    assert result.success is True
    assert result.data == str(expected_path)
    assert expected_path.read_bytes() == b"print('inside')"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlinked_upload_root(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    base_dir = tmp_path / "work"
    base_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    uploads_root = base_dir / "python_uploads"
    try:
        uploads_root.symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(base_dir))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('inside')"),
            UserRequest(user_id="alice"),
        )

    assert exc_info.value.status_code == 400
    assert not (outside_dir / "alice" / "inside.py").exists()
