"""Runtime authorization checks for protected resources."""

import json

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
    AuditEventEntity,
    UserAccountGrantEntity,
    UserResourceGrantEntity,
)
from dbgpt_serve.auth.service.access import (
    AccessService,
    get_access_service,
)
from dbgpt_serve.auth.service.service import Service, get_auth_service
from dbgpt_serve.utils.auth import (
    UserRequest,
    get_current_user,
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
    with db.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS connect_config (id INTEGER PRIMARY KEY, "
                "db_name VARCHAR(255), account_set_id VARCHAR(128))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS knowledge_space (id INTEGER PRIMARY KEY, "
                "name VARCHAR(255), account_set_id VARCHAR(128))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS gpts_app (id INTEGER PRIMARY KEY, "
                "app_code VARCHAR(255), app_name VARCHAR(255), "
                "account_set_id VARCHAR(128))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS gpts_app_detail (id INTEGER PRIMARY KEY, "
                "app_code VARCHAR(255), resources TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS knowledge_document "
                "(id INTEGER PRIMARY KEY, space VARCHAR(255))"
            )
        )
    yield
    db.Model.metadata.drop_all(bind=db.engine)


@pytest.fixture
def access_data():
    with db.session() as session:
        session.add(
            AccountSetEntity(
                account_set_id="account-1",
                name="Account A",
                is_active=True,
                created_by="admin-1",
            )
        )
        for user_id in ("operator-1", "query-1"):
            session.add(
                UserAccountGrantEntity(
                    grant_id=f"account-grant-{user_id}",
                    user_id=user_id,
                    account_set_id="account-1",
                    is_active=True,
                    granted_by="admin-1",
                )
            )
        session.execute(
            text(
                "INSERT INTO connect_config (id, db_name, account_set_id) "
                "VALUES (1, 'sales', 'account-1'), (2, 'unowned', NULL)"
            )
        )
        session.execute(
            text(
                "INSERT INTO knowledge_space (id, name, account_set_id) "
                "VALUES (3, 'manual', 'account-1')"
            )
        )
        session.execute(
            text(
                "INSERT INTO gpts_app (app_code, app_name, account_set_id) "
                "VALUES ('agent-1', 'Sales Agent', 'account-1')"
            )
        )
        session.execute(
            text(
                "INSERT INTO gpts_app_detail (app_code, resources) "
                "VALUES ('agent-1', :resources)"
            ),
            {
                "resources": json.dumps(
                    [
                        {
                            "type": "database",
                            "value": json.dumps({"db_name": "sales"}),
                        }
                    ]
                )
            },
        )
        session.execute(
            text("INSERT INTO knowledge_document (id, space) VALUES (10, 'manual')")
        )


def test_operations_scope_and_system_admin_unassigned_access(access_data):
    service = AccessService()
    operator = UserRequest(user_id="operator-1", role="operations_admin")
    admin = UserRequest(user_id="admin-1", role="system_admin")

    assert (
        service.require_resource_access(
            operator, "DATASOURCE", "sales", manage=True
        ).resource_id
        == "1"
    )
    assert service.allowed_resource_ids(operator, "DATASOURCE") == {"1"}
    assert (
        service.require_resource_access(admin, "DATASOURCE", "2").account_set_id is None
    )
    with pytest.raises(HTTPException) as denied:
        service.require_resource_access(operator, "DATASOURCE", "2")
    assert denied.value.status_code == 403


def test_query_user_requires_concrete_and_agent_dependency_grants(access_data):
    service = AccessService()
    user = UserRequest(user_id="query-1", role="query_user", request_id="request-1")

    with pytest.raises(HTTPException):
        service.require_resource_access(user, "DATASOURCE", "1")
    with db.session() as session:
        session.add(
            UserResourceGrantEntity(
                grant_id="resource-grant-ds",
                user_id="query-1",
                resource_type="DATASOURCE",
                resource_id="1",
                account_set_id="account-1",
                is_active=True,
                granted_by="admin-1",
            )
        )
    assert service.require_resource_access(user, "DATASOURCE", "1").name == "sales"

    with db.session() as session:
        session.add(
            UserResourceGrantEntity(
                grant_id="resource-grant-agent",
                user_id="query-1",
                resource_type="AGENT",
                resource_id="agent-1",
                account_set_id="account-1",
                is_active=True,
                granted_by="admin-1",
            )
        )
    assert (
        service.require_resource_access(user, "AGENT", "agent-1").resource_id
        == "agent-1"
    )
    with db.session() as session:
        datasource_grant = (
            session.query(UserResourceGrantEntity)
            .filter_by(grant_id="resource-grant-ds")
            .one()
        )
        datasource_grant.is_active = False
    with pytest.raises(HTTPException) as denied:
        service.require_resource_access(user, "AGENT", "agent-1")
    assert denied.value.detail["code"] == "AGENT_DEPENDENCY_GRANT_MISSING"
    with db.session(commit=False) as session:
        assert (
            session.query(AuditEventEntity)
            .filter_by(action="AUTHZ.CHECK", request_id="request-1")
            .count()
            >= 2
        )


def test_document_access_resolves_owning_knowledge_space(access_data):
    service = AccessService()
    user = UserRequest(user_id="query-1", role="query_user")
    with db.session() as session:
        session.add(
            UserResourceGrantEntity(
                grant_id="resource-grant-kb",
                user_id="query-1",
                resource_type="KNOWLEDGE_BASE",
                resource_id="3",
                account_set_id="account-1",
                is_active=True,
                granted_by="admin-1",
            )
        )

    assert service.require_document_access(user, "10").resource_id == "3"


def test_fastapi_guard_returns_401_403_and_success(access_data):
    app = FastAPI()

    @app.get("/datasources/{resource_id}")
    async def protected_datasource(
        resource_id: str,
        user: UserRequest = Depends(require_permission("DATASOURCE_USE")),
        access: AccessService = Depends(get_access_service),
    ):
        return access.require_resource_access(
            user, "DATASOURCE", resource_id
        ).resource_id

    app.dependency_overrides[get_auth_service] = lambda: Service(
        None, ServeConfig(jwt_secret=TEST_SECRET)
    )
    client = TestClient(app)
    assert client.get("/datasources/1").status_code == 401

    app.dependency_overrides[get_current_user] = lambda: UserRequest(
        user_id="query-1", role="query_user"
    )
    assert client.get("/datasources/1").status_code == 403
    with db.session() as session:
        session.add(
            UserResourceGrantEntity(
                grant_id="resource-grant-http",
                user_id="query-1",
                resource_type="DATASOURCE",
                resource_id="1",
                account_set_id="account-1",
                is_active=True,
                granted_by="admin-1",
            )
        )
    response = client.get("/datasources/1")
    assert response.status_code == 200
    assert response.json() == "1"
