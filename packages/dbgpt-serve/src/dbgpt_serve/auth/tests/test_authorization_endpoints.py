"""HTTP contract tests for account-set and resource authorization APIs."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.endpoints import router
from dbgpt_serve.auth.api.schemas import AccountSetCreateRequest, UserCreateRequest
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import UserEntity
from dbgpt_serve.auth.service.service import Service, get_auth_service
from dbgpt_serve.utils.auth import UserRequest

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
    with db.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS connect_config ("
                "id INTEGER PRIMARY KEY, db_name VARCHAR(255), "
                "account_set_id VARCHAR(128))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS knowledge_space ("
                "id INTEGER PRIMARY KEY, name VARCHAR(255), "
                "account_set_id VARCHAR(128))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS gpts_app ("
                "id INTEGER PRIMARY KEY, app_code VARCHAR(255), "
                "app_name VARCHAR(255), account_set_id VARCHAR(128))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS gpts_app_detail ("
                "id INTEGER PRIMARY KEY, app_code VARCHAR(255), resources TEXT)"
            )
        )
    yield
    db.Model.metadata.drop_all(bind=db.engine)


@pytest.fixture
def service():
    auth_service = Service(None, ServeConfig(jwt_secret=TEST_SECRET))
    with db.session() as session:
        session.add(
            UserEntity(
                user_id="admin-1",
                login_name="admin",
                display_name="Administrator",
                password_hash=auth_service.hash_password("admin-password"),
                role="system_admin",
                is_active=True,
            )
        )
    return auth_service


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")
    app.dependency_overrides[get_auth_service] = lambda: service
    return TestClient(app, base_url="https://testserver")


def login_headers(client, login_name="admin", password="admin-password"):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": login_name, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": client.cookies["dbgpt_csrf"]}


def setup_scope(service):
    admin = UserRequest(user_id="admin-1", role="system_admin")
    source = service.create_account_set(
        AccountSetCreateRequest(name="Account A"), admin
    )
    target = service.create_account_set(
        AccountSetCreateRequest(name="Account B"), admin
    )
    user = service.create_user(
        UserCreateRequest(
            login_name="alice",
            display_name="Alice",
            role="query_user",
            initial_password="query-password",
        ),
        admin,
    )
    with db.session() as session:
        session.execute(
            text(
                "INSERT INTO connect_config (id, db_name, account_set_id) "
                "VALUES (1, 'sales', :account_set_id)"
            ),
            {"account_set_id": source.account_set_id},
        )
    return source, target, user


def test_grant_and_revoke_contract(client, service):
    source, _, user = setup_scope(service)
    headers = login_headers(client)

    account_response = client.post(
        f"/api/v1/admin/users/{user.user_id}/account-grants",
        headers=headers,
        json={"account_set_id": source.account_set_id},
    )
    assert account_response.status_code == 201, account_response.text
    account_grant = account_response.json()["data"]

    resource_response = client.post(
        f"/api/v1/admin/users/{user.user_id}/resource-grants",
        headers=headers,
        json={"resource_type": "DATASOURCE", "resource_id": "1"},
    )
    assert resource_response.status_code == 201, resource_response.text
    assert resource_response.json()["data"]["account_set_id"] == (source.account_set_id)

    available = client.get(
        f"/api/v1/admin/users/{user.user_id}/resource-grants/available"
    )
    assert available.status_code == 200
    assert available.json()["data"] == []

    impact_response = client.get(
        f"/api/v1/admin/users/{user.user_id}/account-grants/"
        f"{account_grant['grant_id']}/impact"
    )
    impact = impact_response.json()["data"]
    assert impact["affected_resource_grants"] == 1

    unconfirmed = client.request(
        "DELETE",
        f"/api/v1/admin/users/{user.user_id}/account-grants/"
        f"{account_grant['grant_id']}",
        headers=headers,
        json={
            "reason": "Scope removed",
            "confirm_impact": False,
            "impact_token": impact["impact_token"],
        },
    )
    assert unconfirmed.status_code == 409

    revoked = client.request(
        "DELETE",
        f"/api/v1/admin/users/{user.user_id}/account-grants/"
        f"{account_grant['grant_id']}",
        headers=headers,
        json={
            "reason": "Scope removed",
            "confirm_impact": True,
            "impact_token": impact["impact_token"],
        },
    )
    assert revoked.status_code == 200
    assert revoked.json()["data"]["affected_resource_grants"] == 1


def test_resource_assignment_and_scope_errors(client, service):
    source, target, user = setup_scope(service)
    headers = login_headers(client)
    grant_response = client.post(
        f"/api/v1/admin/users/{user.user_id}/account-grants",
        headers=headers,
        json={"account_set_id": source.account_set_id},
    )
    assert grant_response.status_code == 201

    resources = client.get("/api/v1/admin/resources?resource_type=DATASOURCE")
    assert resources.status_code == 200
    assert resources.json()["data"]["items"][0]["resource_id"] == "1"

    impact_response = client.get(
        "/api/v1/admin/resources/DATASOURCE/1/impact",
        params={"new_account_set_id": target.account_set_id},
    )
    assert impact_response.status_code == 200
    impact = impact_response.json()["data"]

    moved = client.patch(
        "/api/v1/admin/resources/DATASOURCE/1/account-set",
        headers=headers,
        json={
            "account_set_id": target.account_set_id,
            "reason": "Ownership changed",
            "confirm_impact": True,
            "impact_token": impact["impact_token"],
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["account_set_id"] == target.account_set_id

    client.cookies.clear()
    query_headers = login_headers(client, "alice", "query-password")
    forbidden = client.get("/api/v1/admin/resources", headers=query_headers)
    assert forbidden.status_code == 403


def test_invalid_resource_type_is_rejected_at_http_boundary(client):
    login_headers(client)
    response = client.get(
        "/api/v1/admin/resources/FILE/1/impact",
        params={"new_account_set_id": "account-1"},
    )
    assert response.status_code == 422
