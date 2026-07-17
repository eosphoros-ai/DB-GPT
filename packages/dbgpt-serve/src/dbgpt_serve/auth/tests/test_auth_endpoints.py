"""HTTP contract tests for authentication endpoints."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.endpoints import router
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import UserEntity
from dbgpt_serve.auth.service.service import Service, get_auth_service
from dbgpt_serve.utils.auth import (
    UserRequest,
    get_current_user,
    get_user_from_headers,
    require_permission,
)

TEST_SECRET = "test-only-jwt-secret-with-at-least-32-bytes"


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db(
        "sqlite://",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    yield
    db.Model.metadata.drop_all(bind=db.engine)


@pytest.fixture
def service():
    auth_service = Service(
        None,
        ServeConfig(
            jwt_secret=TEST_SECRET,
            cookie_secure=True,
            jwt_access_expire_minutes=30,
            jwt_absolute_expire_minutes=120,
        ),
    )
    with db.session() as session:
        session.add(
            UserEntity(
                user_id="user-1",
                login_name="alice",
                display_name="Alice",
                password_hash=auth_service.hash_password("correct-password"),
                role="query_user",
                is_active=True,
            )
        )
    return auth_service


@pytest.fixture
def app(service):
    api = FastAPI()
    api.include_router(router, prefix="/api/v1/admin")
    api.dependency_overrides[get_auth_service] = lambda: service
    return api


@pytest.fixture
def client(app):
    return TestClient(app, base_url="https://testserver")


def test_login_cookie_me_and_logout(client):
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "alice", "password": "correct-password"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["data"]["user"]["user_id"] == "user-1"
    assert login_response.headers["cache-control"] == "no-store"
    assert login_response.headers["pragma"] == "no-cache"
    set_cookie = login_response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=lax" in set_cookie
    csrf_token = client.cookies["dbgpt_csrf"]
    csrf_cookie_header = next(
        header
        for header in login_response.headers.get_list("set-cookie")
        if header.startswith("dbgpt_csrf=")
    ).lower()
    assert "secure" in csrf_cookie_header
    assert "samesite=lax" in csrf_cookie_header
    assert "httponly" not in csrf_cookie_header

    me_response = client.get("/api/v1/admin/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["data"]["role"] == "query_user"
    assert me_response.headers["cache-control"] == "no-store"

    csrf_failure = client.post("/api/v1/admin/auth/logout")
    assert csrf_failure.status_code == 403

    logout_response = client.post(
        "/api/v1/admin/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_response.status_code == 200
    assert logout_response.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_login_failure_does_not_reveal_account_state(client):
    existing = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "alice", "password": "wrong-password"},
    )
    missing = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "missing", "password": "wrong-password"},
    )

    assert existing.status_code == missing.status_code == 401
    assert existing.json()["detail"] == missing.json()["detail"]


def test_login_handles_password_beyond_bcrypt_limit_as_invalid_credentials(client):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "alice", "password": "密" * 25},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid login name or password"
    assert "密" * 25 not in response.text


def test_bearer_token_authentication(client):
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "alice", "password": "correct-password"},
    )
    token = login_response.json()["data"]["access_token"]
    client.cookies.clear()

    response = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    logout_response = client.post(
        "/api/v1/admin/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_response.status_code == 200


def test_legacy_dependency_name_remains_overridable():
    api = FastAPI()

    @api.get("/legacy")
    async def legacy(user: UserRequest = Depends(get_user_from_headers)):
        return {"user_id": user.user_id}

    api.dependency_overrides[get_user_from_headers] = lambda: UserRequest(
        user_id="test-user"
    )
    with TestClient(api) as test_client:
        response = test_client.get("/legacy")

    assert response.status_code == 200
    assert response.json() == {"user_id": "test-user"}


def test_legacy_dependency_no_longer_accepts_mock_user_headers(service):
    api = FastAPI()

    @api.get("/legacy")
    async def legacy(user: UserRequest = Depends(get_user_from_headers)):
        return {"user_id": user.user_id}

    api.dependency_overrides[get_auth_service] = lambda: service
    with TestClient(api) as test_client:
        response = test_client.get("/legacy", headers={"user-id": "admin"})

    assert response.status_code == 401


def test_permission_dependency_uses_fixed_role_capabilities():
    api = FastAPI()

    @api.get("/chat")
    async def chat(
        user: UserRequest = Depends(require_permission("CHAT_USE")),
    ):
        return {"user_id": user.user_id}

    @api.get("/users")
    async def users(
        user: UserRequest = Depends(require_permission("USER_MANAGE")),
    ):
        return {"user_id": user.user_id}

    api.dependency_overrides[get_current_user] = lambda: UserRequest(
        user_id="query-user", role="query_user"
    )
    with TestClient(api) as test_client:
        assert test_client.get("/chat").status_code == 200
        assert test_client.get("/users").status_code == 403
