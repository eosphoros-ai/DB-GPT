from dbgpt_app.openapi.api_view_model import resolve_dialogue_user_name


def test_resolve_dialogue_user_name_preserves_explicit_request_user():
    assert resolve_dialogue_user_name("request_user", "token_user") == "request_user"


def test_resolve_dialogue_user_name_falls_back_to_authenticated_user():
    assert resolve_dialogue_user_name(None, "token_user") == "token_user"
