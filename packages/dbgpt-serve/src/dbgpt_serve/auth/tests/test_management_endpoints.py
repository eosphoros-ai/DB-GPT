"""HTTP contract tests for authorization administration APIs."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.endpoints import router
from dbgpt_serve.auth.api.schemas import ImportCandidateResponse, UserCreateRequest
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import AuditEventEntity, UserEntity
from dbgpt_serve.auth.service.service import Service, get_auth_service
from dbgpt_serve.utils.auth import UserRequest

TEST_SECRET = "test-only-jwt-secret-with-at-least-32-bytes"


class FakeImporter:
    source_name = "erp-directory"

    def preview(self, limit=100):
        return [
            ImportCandidateResponse(
                employee_no="E001",
                name="Imported Alice",
                is_enabled=True,
                category="sales",
                position="manager",
                team="A",
                role_label="query",
            )
        ][:limit]


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
        for table_name in ("connect_config", "knowledge_space", "gpts_app"):
            connection.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {table_name} "
                    "(id INTEGER PRIMARY KEY, account_set_id VARCHAR(128))"
                )
            )
    yield
    db.Model.metadata.drop_all(bind=db.engine)


@pytest.fixture
def service():
    auth_service = Service(
        None,
        ServeConfig(jwt_secret=TEST_SECRET),
        importer=FakeImporter(),
    )
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
def app(service):
    api = FastAPI()
    api.include_router(router, prefix="/api/v1/admin")
    api.dependency_overrides[get_auth_service] = lambda: service
    return api


@pytest.fixture
def client(app):
    return TestClient(app, base_url="https://testserver")


def login_headers(client, login_name="admin", password="admin-password"):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": login_name, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": client.cookies["dbgpt_csrf"]}


def create_account_set(client, headers, name="Account A"):
    response = client.post(
        "/api/v1/admin/account-sets",
        headers=headers,
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def create_query_user(client, headers, account_set_id=None, login_name="alice"):
    body = {
        "login_name": login_name,
        "display_name": "Alice",
        "role": "query_user",
        "initial_password": "correct-password",
    }
    if account_set_id:
        body["initial_account_set_ids"] = [account_set_id]
    response = client.post("/api/v1/admin/users", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_admin_user_and_role_management_contract(client):
    headers = login_headers(client)
    csrf_failure = client.post(
        "/api/v1/admin/users",
        json={
            "login_name": "blocked",
            "display_name": "Blocked",
            "role": "query_user",
            "initial_password": "correct-password",
        },
    )
    assert csrf_failure.status_code == 403

    account_set = create_account_set(client, headers)
    user = create_query_user(client, headers, account_set["account_set_id"])
    assert "password" not in str(user).lower()
    with db.session(commit=False) as session:
        event = (
            session.query(AuditEventEntity)
            .filter_by(action="USER.CREATE", target_id=user["user_id"])
            .one()
        )
        assert event.source_ip == "testclient"
        assert event.user_agent == "testclient"
        assert event.request_id

    list_response = client.get("/api/v1/admin/users?page=1&page_size=20")
    assert list_response.status_code == 200
    assert list_response.headers["cache-control"] == "no-store"
    assert list_response.json()["data"]["total"] == 2

    unconfirmed = client.patch(
        f"/api/v1/admin/users/{user['user_id']}",
        headers=headers,
        json={"role": "operations_admin"},
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["detail"]["code"] == "IMPACT_CONFIRMATION_REQUIRED"

    confirmed = client.patch(
        f"/api/v1/admin/users/{user['user_id']}",
        headers=headers,
        json={
            "role": "operations_admin",
            "change_reason": "Changed responsibilities",
            "confirm_role_change": True,
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["role"] == "operations_admin"

    roles = client.get("/api/v1/admin/roles")
    assert roles.status_code == 200
    assert {item["role"] for item in roles.json()["data"]} == {
        "system_admin",
        "operations_admin",
        "query_user",
    }

    duplicate = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "login_name": "alice",
            "display_name": "Duplicate",
            "role": "query_user",
            "initial_password": "correct-password",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "CONFLICT"
    assert client.get("/api/v1/admin/users?page_size=101").status_code == 422


def test_query_user_cannot_access_management_routes(client, service):
    admin = UserRequest(user_id="admin-1", role="system_admin")
    service.create_user(
        UserCreateRequest(
            login_name="query",
            display_name="Query User",
            role="query_user",
            initial_password="query-password",
        ),
        admin,
    )
    client.cookies.clear()
    headers = login_headers(client, "query", "query-password")

    response = client.post(
        "/api/v1/admin/account-sets",
        headers=headers,
        json={"name": "Forbidden"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


def test_account_set_deactivation_requires_impact_token(client):
    headers = login_headers(client)
    account_set = create_account_set(client, headers)
    create_query_user(client, headers, account_set["account_set_id"])

    impact_response = client.get(
        f"/api/v1/admin/account-sets/{account_set['account_set_id']}/impact"
    )
    impact = impact_response.json()["data"]
    assert impact["user_grant_count"] == 1

    unconfirmed = client.post(
        f"/api/v1/admin/account-sets/{account_set['account_set_id']}/deactivate",
        headers=headers,
        json={
            "reason": "Retired",
            "confirm_impact": False,
            "impact_token": impact["impact_token"],
        },
    )
    assert unconfirmed.status_code == 409

    confirmed = client.post(
        f"/api/v1/admin/account-sets/{account_set['account_set_id']}/deactivate",
        headers=headers,
        json={
            "reason": "Retired",
            "confirm_impact": True,
            "impact_token": impact["impact_token"],
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["is_active"] is False


def test_import_contract_exposes_allowlist_and_password_free_history(client):
    headers = login_headers(client)

    candidates = client.get("/api/v1/admin/import/candidates")
    assert candidates.status_code == 200
    candidate = candidates.json()["data"][0]
    assert set(candidate) == {
        "employee_no",
        "name",
        "is_enabled",
        "category",
        "position",
        "team",
        "role_label",
    }

    batch = client.post(
        "/api/v1/admin/import/batch",
        headers=headers,
        json={
            "users": [
                {
                    "employee_no": "E001",
                    "login_name": "imported-alice",
                    "role": "query_user",
                    "initial_password": "import-password",
                }
            ]
        },
    )
    assert batch.status_code == 201
    assert batch.json()["data"]["created_count"] == 1
    assert "import-password" not in batch.text
    assert "password" not in batch.text.lower()

    history = client.get("/api/v1/admin/import/batches")
    assert history.status_code == 200
    assert history.json()["data"]["total"] == 1
    assert "password" not in history.text.lower()
