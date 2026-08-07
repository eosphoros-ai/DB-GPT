import pytest

from dbgpt_app.openapi.api_view_model import resolve_dialogue_user_name
from dbgpt_serve.utils.auth import UserRequest


def test_resolve_dialogue_user_name_preserves_explicit_request_user():
    assert resolve_dialogue_user_name("request_user", "token_user") == "request_user"


def test_resolve_dialogue_user_name_falls_back_to_authenticated_user():
    assert resolve_dialogue_user_name(None, "token_user") == "token_user"


@pytest.mark.asyncio
async def test_chat_prepare_refreshes_history_with_resolved_dialogue_user(monkeypatch):
    from dbgpt_app.openapi.api_v1 import api_v1
    from dbgpt_app.openapi.api_view_model import ConversationVo

    class FakeChat:
        async def prepare(self):
            return None

    captured = {}

    async def fake_get_chat_instance(dialogue):
        captured["chat_user_name"] = dialogue.user_name
        return FakeChat()

    def fake_get_hist_messages(conv_uid, user_name=None):
        captured["history_conv_uid"] = conv_uid
        captured["history_user_name"] = user_name
        return ["history"]

    monkeypatch.setattr(api_v1, "get_chat_instance", fake_get_chat_instance)
    monkeypatch.setattr(api_v1, "get_hist_messages", fake_get_hist_messages)

    result = await api_v1.chat_prepare(
        ConversationVo(conv_uid="conv-1", user_name="request_user"),
        UserRequest(user_id="token_user"),
    )

    assert result.data == ["history"]
    assert captured == {
        "chat_user_name": "request_user",
        "history_conv_uid": "conv-1",
        "history_user_name": "request_user",
    }
