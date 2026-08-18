import pytest
from fastapi import HTTPException

from dbgpt_serve.utils import auth


def test_get_user_from_headers_allows_compat_when_no_api_keys(monkeypatch):
    monkeypatch.setattr(auth, "_get_configured_api_keys", lambda: [])

    user = auth.get_user_from_headers(user_id=None, authorization=None)

    assert user.user_id == "001"
    assert user.role == "admin"


def test_get_user_from_headers_rejects_missing_bearer_when_api_keys_configured(
    monkeypatch,
):
    monkeypatch.setattr(auth, "_get_configured_api_keys", lambda: ["secret"])

    with pytest.raises(HTTPException) as exc_info:
        auth.get_user_from_headers(user_id=None, authorization=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "invalid_api_key"


def test_get_user_from_headers_rejects_wrong_bearer_when_api_keys_configured(
    monkeypatch,
):
    monkeypatch.setattr(auth, "_get_configured_api_keys", lambda: ["secret"])

    with pytest.raises(HTTPException) as exc_info:
        auth.get_user_from_headers(user_id=None, authorization="Bearer wrong")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "invalid_api_key"


def test_get_user_from_headers_accepts_valid_bearer_when_api_keys_configured(
    monkeypatch,
):
    monkeypatch.setattr(auth, "_get_configured_api_keys", lambda: ["secret"])

    user = auth.get_user_from_headers(user_id="alice", authorization="Bearer secret")

    assert user.user_id == "alice"
    assert user.role == "admin"
