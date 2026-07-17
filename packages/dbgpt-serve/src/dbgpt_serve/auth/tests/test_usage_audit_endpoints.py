"""HTTP contracts for usage and audit administration APIs."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.endpoints import router
from dbgpt_serve.auth.api.schemas import AuditEventCreate, TokenUsageCreate
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import UserEntity
from dbgpt_serve.auth.service.audit_service import AuditService, get_audit_service
from dbgpt_serve.auth.service.service import Service, get_auth_service
from dbgpt_serve.auth.service.token_service import TokenService, get_token_service

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
def services():
    auth_service = Service(None, ServeConfig(jwt_secret=TEST_SECRET))
    with db.session() as session:
        session.add_all(
            [
                UserEntity(
                    user_id="admin-1",
                    login_name="admin",
                    display_name="Administrator",
                    password_hash=auth_service.hash_password("admin-password"),
                    role="system_admin",
                    is_active=True,
                ),
                UserEntity(
                    user_id="query-1",
                    login_name="query",
                    display_name="Query User",
                    password_hash=auth_service.hash_password("query-password"),
                    role="query_user",
                    is_active=True,
                ),
            ]
        )
    token_service = TokenService()
    audit_service = AuditService()
    token_service.record_usage(
        TokenUsageCreate(
            call_id="call-1",
            request_id="request-1",
            user_id="query-1",
            role_snapshot="query_user",
            model="gpt-test",
            input_tokens=10,
            output_tokens=2,
            total_tokens=12,
            metering_source="provider",
            status="success",
            gmt_created=datetime(2026, 7, 17, 1, 0, tzinfo=timezone.utc),
        )
    )
    audit_service.record(
        AuditEventCreate(
            event_time=datetime(2026, 7, 17, 1, 0),
            operator_user_id="admin-1",
            operator_role_snapshot="system_admin",
            target_type="USER",
            target_id="query-1",
            action="USER.TEST",
            result="success",
        )
    )
    return auth_service, token_service, audit_service


@pytest.fixture
def client(services):
    auth_service, token_service, audit_service = services
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/admin")
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_token_service] = lambda: token_service
    app.dependency_overrides[get_audit_service] = lambda: audit_service
    return TestClient(app, base_url="https://testserver")


def login(client, login_name, password):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": login_name, "password": password},
    )
    assert response.status_code == 200, response.text


def test_admin_usage_and_audit_contract(client):
    login(client, "admin", "admin-password")

    detail = client.get("/api/v1/admin/token-usage/detail")
    assert detail.status_code == 200
    assert detail.json()["data"]["total"] == 1
    daily = client.get(
        "/api/v1/admin/token-usage/daily",
        params={"date_from": "2026-07-17", "date_to": "2026-07-17"},
    )
    assert daily.status_code == 200
    assert daily.json()["data"][0]["total_tokens"] == 12
    summary = client.get(
        "/api/v1/admin/token-usage/summary",
        params={"stat_date": "2026-07-17"},
    )
    assert summary.json()["data"]["call_count"] == 1

    audit = client.get("/api/v1/admin/audit", params={"action": "USER.TEST"})
    assert audit.status_code == 200
    event = audit.json()["data"]["items"][0]
    assert event["target_id"] == "query-1"
    assert client.get(f"/api/v1/admin/audit/{event['event_id']}").status_code == 200
    assert client.delete(f"/api/v1/admin/audit/{event['event_id']}").status_code == 405


def test_query_user_sees_only_self_usage_and_not_audit(client):
    login(client, "query", "query-password")

    own = client.get("/api/v1/admin/token-usage/detail")
    assert own.status_code == 200
    assert own.json()["data"]["items"][0]["user_id"] == "query-1"
    assert client.get("/api/v1/admin/audit").status_code == 403
