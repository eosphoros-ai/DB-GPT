import pytest

from dbgpt_serve.utils.auth import UserRequest


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content_type = "text/x-python"
        self._content = content

    async def read(self) -> bytes:
        return self._content


def _configure_skill_paths(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    upload_dir = tmp_path / "pilot" / "tmp"
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(
        agentic_data_api, "resolve_root_path", lambda _: str(upload_dir)
    )
    monkeypatch.setattr(agentic_data_api, "DEFAULT_SKILLS_DIR", str(skills_dir))
    return agentic_data_api, upload_dir, skills_dir


@pytest.mark.asyncio
async def test_skill_upload_rejects_traversal_filename(tmp_path, monkeypatch):
    agentic_data_api, _, skills_dir = _configure_skill_paths(tmp_path, monkeypatch)

    result = await agentic_data_api.skill_upload(
        FakeUploadFile("../../outside.py", b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "outside.py").exists()
    assert not (skills_dir / "outside.py").exists()


@pytest.mark.asyncio
async def test_skill_upload_rejects_absolute_filename(tmp_path, monkeypatch):
    agentic_data_api, _, _ = _configure_skill_paths(tmp_path, monkeypatch)
    outside_path = tmp_path / "outside.py"

    result = await agentic_data_api.skill_upload(
        FakeUploadFile(str(outside_path), b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not outside_path.exists()


@pytest.mark.asyncio
async def test_skill_upload_rejects_windows_path_separator(tmp_path, monkeypatch):
    agentic_data_api, upload_dir, skills_dir = _configure_skill_paths(
        tmp_path, monkeypatch
    )

    result = await agentic_data_api.skill_upload(
        FakeUploadFile(r"..\outside.py", b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (upload_dir / r"..\outside.py").exists()
    assert not (skills_dir / "user" / "outside.py").exists()


@pytest.mark.asyncio
async def test_skill_upload_accepts_plain_filename(tmp_path, monkeypatch):
    agentic_data_api, upload_dir, skills_dir = _configure_skill_paths(
        tmp_path, monkeypatch
    )

    result = await agentic_data_api.skill_upload(
        FakeUploadFile("hello.py", b"print('hello')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is True
    assert result.data["file_path"] == "user/hello"
    assert result.data["tmp_path"] == str(upload_dir / "hello.py")
    assert (upload_dir / "hello.py").read_bytes() == b"print('hello')"
    assert (
        skills_dir / "user" / "hello" / "hello.py"
    ).read_bytes() == b"print('hello')"
