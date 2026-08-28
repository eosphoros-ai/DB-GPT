import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from dbgpt_serve.utils.auth import UserRequest


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content_type = "text/x-python"
        self._buffer = io.BytesIO(content)
        self.read_calls = []

    async def read(self, size: int = -1) -> bytes:
        self.read_calls.append(size)
        return self._buffer.read(size)


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


@pytest.mark.parametrize(
    "filename",
    ["..\\..\\evil.py", "sub\\nested.py", "..\\evil.py"],
)
@pytest.mark.asyncio
async def test_python_file_upload_rejects_windows_separators(
    tmp_path, monkeypatch, filename
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile(filename, b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    owner_root = tmp_path / "python_uploads" / "alice"
    leftovers = list(owner_root.rglob("*")) if owner_root.exists() else []
    assert not any(path.is_file() for path in leftovers)


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
async def test_python_file_upload_rejects_other_owner_traversal(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("../bob/secret.py", b"print('cross-owner')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "python_uploads" / "bob").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlinked_owner_root(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    uploads_root = tmp_path / "python_uploads"
    uploads_root.mkdir(parents=True)
    escape_dir = tmp_path / "escape"
    escape_dir.mkdir()
    try:
        (uploads_root / "mallory").symlink_to(escape_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('escaped')"),
            UserRequest(user_id="mallory"),
        )

    assert exc_info.value.status_code == 400
    assert not (escape_dir / "inside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_traversing_owner_id(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('escaped')"),
            UserRequest(user_id="../evil"),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_python_file_upload_never_overwrites_via_symlink(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    upload_dir.mkdir(parents=True)
    target = upload_dir / "target.py"
    target.write_bytes(b"original")
    try:
        (upload_dir / "link.py").symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("link.py", b"print('overwritten')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert target.read_bytes() == b"original"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlinked_parent_component(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    real_dir = upload_dir / "real"
    real_dir.mkdir(parents=True)
    try:
        (upload_dir / "linkdir").symlink_to(real_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("linkdir/renamed.py", b"print('renamed target')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (real_dir / "renamed.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_reads_and_writes_in_bounded_chunks(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    payload = (b"chunked-payload " * 12000) + b"tail"
    upload = FakeUploadFile("script.py", payload)

    result = await python_upload_api.python_file_upload(
        upload,
        UserRequest(user_id="alice"),
    )

    expected_path = tmp_path / "python_uploads" / "alice" / "script.py"
    assert result.success is True
    assert expected_path.read_bytes() == payload
    assert upload.read_calls, "upload must be read at least once"
    assert all(0 < size for size in upload.read_calls[:-1])
    assert max(upload.read_calls[:-1]) <= python_upload_api._UPLOAD_CHUNK_BYTES


@pytest.mark.asyncio
async def test_python_file_upload_overwrites_existing_regular_file(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    upload_dir.mkdir(parents=True)
    existing = upload_dir / "inside.py"
    existing.write_bytes(b"old content")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b"new content"),
        UserRequest(user_id="alice"),
    )

    assert result.success is True
    assert result.data == str(existing)
    assert existing.read_bytes() == b"new content"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_empty_file_without_touching_disk(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    upload_dir.mkdir(parents=True)
    existing = upload_dir / "inside.py"
    existing.write_bytes(b"old content")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b""),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert existing.read_bytes() == b"old content"


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
