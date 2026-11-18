"""Session file ownership follows the verified v1 principal, not headers."""

import hashlib
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file.api import endpoints as endpoints_module
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401
from dbgpt_serve.utils.auth import v1_auth_middleware

PREFIX = "/api/v1/agent/files"
ALICE = {"user-id": "alice"}
GOOD_KEY = {"Authorization": "Bearer secret-key-1"}
BAD_KEY = {"Authorization": "Bearer wrong-key"}
OWNER_1 = "key-" + hashlib.sha256(b"secret-key-1").hexdigest()
OWNER_2 = "key-" + hashlib.sha256(b"secret-key-2").hexdigest()


class _EmptyListService:
    """Minimal storage seam double; auth rejections never reach the service."""

    def ingest(self, **kwargs):
        raise AssertionError("ingest must not be reached by these auth tests")

    def list_files(self, *, owner_id, session_id):
        return []

    def get_file(self, *, owner_id, session_id, file_id):
        return None

    def open_download(self, *, owner_id, session_id, file_id):
        return None

    def delete_file(self, *, owner_id, session_id, file_id):
        return False


@pytest.fixture(autouse=True)
def _isolate_module_state():
    endpoints_module._reset_endpoints()
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    yield
    endpoints_module._reset_endpoints()


@pytest.fixture()
def client():
    config = ServeConfig(api_keys="secret-key-1,secret-key-2")
    app = FastAPI()
    app.state.api_keys = ("secret-key-1", "secret-key-2")
    app.middleware("http")(v1_auth_middleware)
    app.include_router(endpoints_module.router, prefix=PREFIX)
    app.state.spy = _SpyListService()
    endpoints_module.init_endpoints(MagicMock(), app.state.spy, config)
    return TestClient(app)


def _assert_auth_error(response):
    assert response.status_code == 401, response.text
    assert "detail" in response.json()


def test_missing_bearer_token_is_rejected_when_api_keys_configured(client):
    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)

    _assert_auth_error(response)


def test_wrong_bearer_token_is_rejected(client):
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={**ALICE, **BAD_KEY},
    )

    _assert_auth_error(response)


def test_valid_key_without_user_id_uses_verified_owner(client):
    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=GOOD_KEY)
    assert response.status_code == 200, response.text
    assert client.app.state.spy.seen_owners[0] == OWNER_1


def test_valid_key_with_blank_user_id_uses_verified_owner(client):
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={"user-id": "   ", **GOOD_KEY},
    )

    assert response.status_code == 200, response.text
    assert client.app.state.spy.seen_owners[0] == OWNER_1


def test_valid_key_and_valid_user_id_is_accepted(client):
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={**ALICE, **GOOD_KEY},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == []
    assert client.app.state.spy.seen_owners[0] == OWNER_1


def test_overlong_caller_header_does_not_change_verified_owner(client):
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={"user-id": "o" * 129, **GOOD_KEY},
    )

    assert response.status_code == 200, response.text
    assert client.app.state.spy.seen_owners[0] == OWNER_1


def test_raw_header_bytes_do_not_change_verified_owner(client):
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers=[
            (b"user-id", b"\xe9" * 129),
            (b"Authorization", b"Bearer secret-key-1"),
        ],
    )

    assert response.status_code == 200, response.text
    assert client.app.state.spy.seen_owners[0] == OWNER_1


def test_distinct_verified_keys_have_distinct_owners(client):
    client.get(PREFIX, params={"session_id": "conv-1"}, headers=GOOD_KEY)
    client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={"Authorization": "Bearer secret-key-2", **ALICE},
    )
    first, second = client.app.state.spy.seen_owners
    assert (first, second) == (OWNER_1, OWNER_2)


class _SpyListService(_EmptyListService):
    """Record the owner passed through auth into the service seam."""

    def __init__(self):
        self.seen_owners = []

    def list_files(self, *, owner_id, session_id):
        self.seen_owners.append(owner_id)
        return []


@pytest.fixture()
def anon_client():
    config = ServeConfig()
    app = FastAPI()
    app.state.api_keys = ()
    app.middleware("http")(v1_auth_middleware)
    app.include_router(endpoints_module.router, prefix=PREFIX)
    spy = _SpyListService()
    endpoints_module.init_endpoints(MagicMock(), spy, config)
    return TestClient(app), spy


def test_anonymous_mode_missing_user_id_falls_back_to_shared_owner(anon_client):
    client, spy = anon_client

    response = client.get(PREFIX, params={"session_id": "conv-1"})

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert spy.seen_owners == ["001"]


def test_anonymous_mode_blank_user_id_falls_back_to_shared_owner(anon_client):
    client, spy = anon_client

    response = client.get(
        PREFIX, params={"session_id": "conv-1"}, headers={"user-id": "   "}
    )

    assert response.status_code == 200, response.text
    assert spy.seen_owners == ["001"]


def test_anonymous_mode_explicit_user_id_does_not_change_shared_owner(anon_client):
    client, spy = anon_client

    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)

    assert response.status_code == 200, response.text
    assert spy.seen_owners == ["001"]
