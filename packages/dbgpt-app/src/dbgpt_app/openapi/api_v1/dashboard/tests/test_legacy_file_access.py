from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_owned_legacy_file_and_current_upload_remain_available(
    tmp_path, monkeypatch
):
    from dbgpt.storage.chat_history.chat_history_db import ChatHistoryDao
    from dbgpt_app.openapi.api_v1 import uploaded_dataset_registry
    from dbgpt_app.openapi.api_v1.api_v1 import (
        _authorize_local_user_file,
        file_delete,
        file_read,
    )
    from dbgpt_serve.utils.auth import UserRequest

    monkeypatch.setattr(uploaded_dataset_registry, "upload_work_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.KNOWLEDGE_UPLOAD_ROOT_PATH", str(tmp_path)
    )
    monkeypatch.setattr(
        "dbgpt.util.file_client.KNOWLEDGE_UPLOAD_ROOT_PATH", str(tmp_path)
    )
    monkeypatch.setattr(
        ChatHistoryDao,
        "get_by_uid",
        lambda self, uid: SimpleNamespace(user_name="alice"),
    )
    legacy = tmp_path / "conversation-1" / "legacy.csv"
    legacy.parent.mkdir()
    legacy.write_text("value\n1\n")
    current = tmp_path / "python_uploads" / "alice" / "current.csv"
    current.parent.mkdir(parents=True)
    current.write_text("value\n2\n")
    assert _authorize_local_user_file("conversation-1", str(legacy), "alice") == str(
        legacy.resolve()
    )
    assert _authorize_local_user_file("conversation-1", str(current), "alice") == str(
        current.resolve()
    )
    for path in (legacy, current):
        with pytest.raises(HTTPException) as error:
            _authorize_local_user_file("conversation-1", str(path), "bob")
        assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        _authorize_local_user_file("../conversation-1", str(legacy), "alice")
    response = await file_read(
        "conversation-1", str(legacy), user_token=UserRequest(user_id="alice")
    )
    assert response.success and response.data == '[{"value":1}]'
    deleted = await file_delete(
        "conversation-1", str(legacy), user_token=UserRequest(user_id="alice")
    )
    assert deleted.success and not legacy.exists()
