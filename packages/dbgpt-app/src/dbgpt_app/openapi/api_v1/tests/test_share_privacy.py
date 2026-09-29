from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from dbgpt_serve.utils.auth import UserRequest


class MemoryShareDao:
    def __init__(self):
        self.link = None

    def create_share(self, conv_uid, created_by=None):
        if self.link is None:
            self.link = SimpleNamespace(
                token="opaque-token",
                conv_uid=conv_uid,
                created_by=created_by,
            )
        return self.link

    def get_by_conv_uid(self, conv_uid):
        return self.link if self.link and self.link.conv_uid == conv_uid else None

    def get_by_token(self, token):
        return self.link if self.link and self.link.token == token else None

    def delete_by_token(self, token):
        if self.get_by_token(token) is None:
            return False
        self.link = None
        return True


class MemoryConversationService:
    def get(self, request):
        if request.conv_uid == "conversation-1" and request.user_name == "alice":
            return SimpleNamespace(conv_uid=request.conv_uid)
        return None

    def get_history_messages(self, request):
        return [
            SimpleNamespace(
                role="view",
                order=1,
                context=(
                    "loaded C:\\work\\python_uploads\\alice\\batch-1\\orders.csv "
                    "from upload_alice_secret123"
                ),
            )
        ]


@pytest.mark.asyncio
async def test_share_creation_and_revocation_are_owner_scoped(monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    dao = MemoryShareDao()
    monkeypatch.setattr(agentic_data_api, "_get_share_dao", lambda: dao)
    monkeypatch.setattr(
        agentic_data_api,
        "_get_conversation_service",
        lambda: MemoryConversationService(),
    )

    created = await agentic_data_api.create_share_link(
        agentic_data_api.ShareCreateRequest(conv_uid="conversation-1"),
        UserRequest(user_id="alice"),
    )
    assert created.success is True

    with pytest.raises(HTTPException) as create_error:
        await agentic_data_api.create_share_link(
            agentic_data_api.ShareCreateRequest(conv_uid="conversation-1"),
            UserRequest(user_id="bob"),
        )
    assert create_error.value.status_code == 404

    with pytest.raises(HTTPException) as delete_error:
        await agentic_data_api.delete_share_link(
            "opaque-token", UserRequest(user_id="bob")
        )
    assert delete_error.value.status_code == 404
    assert dao.link is not None

    deleted = await agentic_data_api.delete_share_link(
        "opaque-token", UserRequest(user_id="alice")
    )
    assert deleted.success is True


@pytest.mark.asyncio
async def test_public_share_redacts_server_paths_and_upload_identifiers(monkeypatch):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    dao = MemoryShareDao()
    dao.create_share("conversation-1", "alice")
    monkeypatch.setattr(agentic_data_api, "_get_share_dao", lambda: dao)
    monkeypatch.setattr(
        agentic_data_api,
        "_get_conversation_service",
        lambda: MemoryConversationService(),
    )

    result = await agentic_data_api.get_share_conversation("opaque-token")
    context = result.data.messages[0]["context"]
    assert "python_uploads" not in context
    assert "orders.csv" not in context
    assert "upload_alice_secret123" not in context
    assert "[uploaded file]" in context
    assert "[uploaded dataset]" in context
