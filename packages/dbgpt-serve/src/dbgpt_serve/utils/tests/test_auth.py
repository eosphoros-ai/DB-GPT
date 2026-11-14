from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dbgpt_serve.utils.auth import (
    UserRequest,
    get_user_from_headers,
    v1_auth_middleware,
)


def _client(api_keys):
    app = FastAPI()
    app.state.api_keys = api_keys

    @app.get("/api/v1/identity")
    def identity(user: UserRequest = Depends(get_user_from_headers)):
        return {"user_id": user.user_id, "role": user.role}

    return TestClient(app)


def test_configured_keys_reject_missing_and_invalid_bearer_tokens():
    client = _client("key-a,key-b")
    assert (
        client.get("/api/v1/identity", headers={"user-id": "alice"}).status_code == 401
    )
    assert (
        client.get(
            "/api/v1/identity",
            headers={"Authorization": "Bearer unknown", "user-id": "alice"},
        ).status_code
        == 401
    )


def test_verified_key_determines_identity_not_caller_header():
    client = _client("key-a,key-b")
    first = client.get(
        "/api/v1/identity",
        headers={"Authorization": "Bearer key-a", "user-id": "alice"},
    )
    second = client.get(
        "/api/v1/identity",
        headers={"Authorization": "Bearer key-a", "user-id": "bob"},
    )
    other = client.get("/api/v1/identity", headers={"Authorization": "Bearer key-b"})

    assert first.status_code == second.status_code == other.status_code == 200
    assert first.json() == second.json()
    assert first.json()["user_id"] not in {"alice", "bob", "key-a", "001"}
    assert first.json()["user_id"] != other.json()["user_id"]
    assert first.json()["role"] == other.json()["role"] == "normal"


def test_unconfigured_keys_use_shared_least_privilege_identity():
    client = _client(None)
    response = client.get("/api/v1/identity", headers={"user-id": "alice"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "001", "role": "normal"}


def test_v1_middleware_guards_routes_without_identity_dependency():
    app = FastAPI()
    app.state.api_keys = ("key-a",)

    app.middleware("http")(v1_auth_middleware)

    @app.get("/api/v1/unguarded")
    def v1_route():
        return {"reached": True}

    @app.get("/api/v2/unguarded")
    def v2_route():
        return {"reached": True}

    client = TestClient(app)
    assert client.get("/api/v1/unguarded").status_code == 401
    assert (
        client.get(
            "/api/v1/unguarded", headers={"Authorization": "Bearer key-a"}
        ).status_code
        == 200
    )
    assert client.get("/api/v2/unguarded").status_code == 200
