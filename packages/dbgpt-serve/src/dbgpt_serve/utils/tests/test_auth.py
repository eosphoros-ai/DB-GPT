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


def test_service_keys_are_scoped_and_global_keys_remain_valid():
    app = FastAPI()
    app.state.api_keys = ("global",)
    app.middleware("http")(v1_auth_middleware)

    @app.get("/api/v1/serve/awel/test")
    def flow(user: UserRequest = Depends(get_user_from_headers)):
        return {"owner": user.user_id}

    @app.get("/api/v1/agent/files/test")
    def files(user: UserRequest = Depends(get_user_from_headers)):
        return {"owner": user.user_id}

    @app.get("/api/v1/agent/files/download")
    def legacy_agent_download(user: UserRequest = Depends(get_user_from_headers)):
        return {"owner": user.user_id}

    @app.get("/api/v1/chat/dialogue/scenes")
    def legacy_chat_scenes(user: UserRequest = Depends(get_user_from_headers)):
        return {"owner": user.user_id}

    scoped = {
        "/api/v1/serve/awel/test": ("global", "flow-key"),
        "/api/v1/agent/files/test": ("global", "files-key"),
    }
    app.state.api_keys_by_route = [
        (route.path_regex, route.methods, scoped.get(route.path, ("global",)))
        for route in app.routes
        if hasattr(route, "path_regex")
    ]

    client = TestClient(app)
    flow_owner = client.get(
        "/api/v1/serve/awel/test", headers={"Authorization": "Bearer flow-key"}
    )
    assert flow_owner.status_code == 200
    assert flow_owner.json()["owner"] != "001"
    assert (
        client.get(
            "/api/v1/agent/files/test", headers={"Authorization": "Bearer flow-key"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/serve/awel/test", headers={"Authorization": "Bearer global"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/serve/awel/test", headers={"Authorization": "Bearer files-key"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/agent/files/download",
            headers={"Authorization": "Bearer files-key"},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/agent/files/download",
            headers={"Authorization": "Bearer global"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/chat/dialogue/scenes",
            headers={"Authorization": "Bearer conversation-key"},
        ).status_code
        == 401
    )


def test_public_share_methods_do_not_disable_protected_methods():
    app = FastAPI()
    app.state.api_keys = ("key",)
    app.middleware("http")(v1_auth_middleware)

    @app.get("/api/v1/chat/share/{token}")
    def read_share(token: str):
        return {"token": token}

    @app.delete("/api/v1/chat/share/{token}")
    def delete_share(token: str):
        return {"token": token}

    @app.post("/api/v1/public/dashboards/{token}/filter")
    def filter_share(token: str):
        return {"token": token}

    client = TestClient(app)
    assert client.get("/api/v1/chat/share/a").status_code == 200
    assert client.post("/api/v1/public/dashboards/a/filter").status_code == 200
    assert client.delete("/api/v1/chat/share/a").status_code == 401
    assert (
        client.delete(
            "/api/v1/chat/share/a", headers={"Authorization": "Bearer key"}
        ).status_code
        == 200
    )


def test_development_fallback_keeps_distinct_markers():
    app = FastAPI()
    app.state.api_keys = ()

    @app.get("/api/v1/identity")
    def identity(user: UserRequest = Depends(get_user_from_headers)):
        return user.model_dump()

    user = TestClient(app).get("/api/v1/identity").json()
    assert user["user_id"] == "001"
    assert user["real_name"] == user["nick_name"] == "dbgpt"


def test_service_only_keys_do_not_leave_other_v1_routes_anonymous():
    app = FastAPI()
    app.state.api_keys = ()
    app.state.v1_api_keys_configured = True
    app.middleware("http")(v1_auth_middleware)

    @app.get("/api/v1/serve/awel/test")
    def flow():
        return {"reached": True}

    @app.get("/api/v1/general")
    def general():
        return {"reached": True}

    app.state.api_keys_by_route = [
        (
            route.path_regex,
            route.methods,
            ("flow-key",) if route.path.endswith("awel/test") else (),
        )
        for route in app.routes
        if hasattr(route, "path_regex")
    ]
    client = TestClient(app)
    assert client.get("/api/v1/serve/awel/test").status_code == 401
    assert (
        client.get(
            "/api/v1/serve/awel/test",
            headers={"Authorization": "Bearer flow-key"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/general").status_code == 401
    assert (
        client.get(
            "/api/v1/general", headers={"Authorization": "Bearer flow-key"}
        ).status_code
        == 401
    )
