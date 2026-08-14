"""Authentication contract tests for the session file API.

Session file routes consume configured ``api_keys`` exactly like the
existing serves (see ``dbgpt_serve.file.api.endpoints``): when
``config.api_keys`` is set, a valid ``Bearer`` token is required regardless
of user headers and a missing or blank ``user-id`` header is always a 401;
when it is not set (anonymous lightweight deployments), requests are allowed
through key checking and a missing or blank ``user-id`` header falls back to
the codebase-wide shared owner ``"001"``, matching
``get_user_from_headers`` behavior everywhere else. Clients still never
control the owner: any anomaly in ``user-id`` (overlong etc.) is rejected
before the registry.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file.api import endpoints as endpoints_module
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401

PREFIX = "/api/v1/agent/files"
ALICE = {"user-id": "alice"}
GOOD_KEY = {"Authorization": "Bearer secret-key-1"}
BAD_KEY = {"Authorization": "Bearer wrong-key"}


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
    app.include_router(endpoints_module.router, prefix=PREFIX)
    endpoints_module.init_endpoints(MagicMock(), _EmptyListService(), config)
    return TestClient(app)


def _assert_auth_error(response):
    assert response.status_code == 401, response.text
    payload = response.json()
    assert payload["success"] is False
    assert payload["err_code"] == "MISSING_AUTH_OWNER"


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


def test_valid_key_without_user_id_is_rejected(client):
    # The shared auth util would fall back to a mock "001" owner here; the
    # session file module must never do that.
    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=GOOD_KEY)

    _assert_auth_error(response)


def test_valid_key_with_blank_user_id_is_rejected(client):
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={"user-id": "   ", **GOOD_KEY},
    )

    _assert_auth_error(response)


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


def test_overlong_owner_is_rejected_before_registry(client):
    # Persistence/materialization cap scope components at 128 bytes; the
    # transport must reject overlong owners before any registry call.
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers={"user-id": "o" * 129, **GOOD_KEY},
    )

    _assert_auth_error(response)


def test_owner_is_capped_in_raw_header_bytes(client):
    # 129 raw header bytes decode to 129 latin-1 characters: over the cap
    # whether counted as bytes or as decoded characters.
    response = client.get(
        PREFIX,
        params={"session_id": "conv-1"},
        headers=[
            (b"user-id", b"\xe9" * 129),
            (b"Authorization", b"Bearer secret-key-1"),
        ],
    )

    _assert_auth_error(response)


class _SpyListService(_EmptyListService):
    """Record the owner passed through auth into the service seam."""

    def __init__(self):
        self.seen_owners = []

    def list_files(self, *, owner_id, session_id):
        self.seen_owners.append(owner_id)
        return []


@pytest.fixture()
def anon_client():
    # Anonymous mode: the server has no api_keys configured. The session file
    # module must mirror the codebase-wide anonymous identity behavior from
    # ``get_user_from_headers`` (missing/blank user-id -> shared owner "001").
    config = ServeConfig()
    app = FastAPI()
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


def test_anonymous_mode_explicit_user_id_is_used_without_bearer(anon_client):
    client, spy = anon_client

    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)

    assert response.status_code == 200, response.text
    assert spy.seen_owners == ["alice"]
