import pytest

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
    assert result.data == target_path.as_posix()
    assert target_path.read_text(encoding="utf-8") == "value\n1\n"


@pytest.mark.asyncio
async def test_example_response_is_accepted_by_legacy_chat_input(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        AttachmentInputError,
        parse_chat_file_input,
        resolve_legacy_chat_file_path,
    )

    examples_api = _configure_example(tmp_path, monkeypatch, "report.csv")
    result = await examples_api.use_example_file(
        "test_example", UserRequest(user_id="alice")
    )

    assert result.success is True
    parse_chat_file_input({"file_path": result.data})
    resolved = resolve_legacy_chat_file_path(
        file_path=result.data, owner_id="alice", base_dir=str(tmp_path)
    )
    assert resolved == str((tmp_path / "python_uploads/alice/report.csv").resolve())

    # The generated path remains owner-bound when passed back to chat.
    with pytest.raises(AttachmentInputError) as exc_info:
        resolve_legacy_chat_file_path(
            file_path=result.data, owner_id="bob", base_dir=str(tmp_path)
        )
    assert exc_info.value.status_code == 404
