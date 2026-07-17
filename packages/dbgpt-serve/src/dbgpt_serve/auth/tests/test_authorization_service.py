"""Transactional tests for account-set and resource authorization management."""

import json

import pytest
from sqlalchemy import text

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.schemas import (
    AccountSetCreateRequest,
    AssignResourceAccountRequest,
    ConfirmRevokeRequest,
    RevokeRequest,
    UserCreateRequest,
)
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import (
    UserAccountGrantDao,
    UserAccountGrantEntity,
    UserEntity,
    UserResourceGrantDao,
    UserResourceGrantEntity,
)
from dbgpt_serve.auth.service.errors import (
    ImpactConfirmationRequiredError,
    ManagementValidationError,
)
from dbgpt_serve.auth.service.service import Service
from dbgpt_serve.utils.auth import UserRequest

TEST_SECRET = "test-only-jwt-secret-with-at-least-32-bytes"


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
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
    return Service(None, ServeConfig(jwt_secret=TEST_SECRET))


@pytest.fixture
def admin(service):
    with db.session() as session:
        session.add(
            UserEntity(
                user_id="admin-1",
                login_name="admin",
                display_name="Administrator",
                password_hash=service.hash_password("admin-password"),
                role="system_admin",
                is_active=True,
            )
        )
    return UserRequest(user_id="admin-1", role="system_admin")


def create_account_set(service, admin, name):
    return service.create_account_set(AccountSetCreateRequest(name=name), admin)


def create_user(service, admin, login_name, role="query_user"):
    return service.create_user(
        UserCreateRequest(
            login_name=login_name,
            display_name=login_name.title(),
            role=role,
            initial_password="correct-password",
        ),
        admin,
    )


def insert_resource(table_name, resource_id, name_column, name, account_set_id=None):
    id_column = "app_code" if table_name == "gpts_app" else "id"
    with db.session() as session:
        session.execute(
            text(
                f"INSERT INTO {table_name} "
                f"({id_column}, {name_column}, account_set_id) "
                "VALUES (:resource_id, :name, :account_set_id)"
            ),
            {
                "resource_id": resource_id,
                "name": name,
                "account_set_id": account_set_id,
            },
        )


def test_account_grant_revoke_cascades_resource_grants(service, admin):
    account_set = create_account_set(service, admin, "Account A")
    user = create_user(service, admin, "alice")
    insert_resource("connect_config", 1, "db_name", "sales", account_set.account_set_id)

    account_grant = service.grant_user_account(
        user.user_id, account_set.account_set_id, admin
    )
    resource_grant = service.grant_user_resource(user.user_id, "DATASOURCE", "1", admin)
    impact = service.get_user_account_revoke_impact(
        user.user_id, account_grant.grant_id, admin
    )

    assert impact.affected_resource_grants == 1
    with pytest.raises(ImpactConfirmationRequiredError):
        service.revoke_user_account(
            user.user_id,
            account_grant.grant_id,
            ConfirmRevokeRequest(
                reason="Scope removed",
                confirm_impact=False,
                impact_token=impact.impact_token,
            ),
            admin,
        )

    service.revoke_user_account(
        user.user_id,
        account_grant.grant_id,
        ConfirmRevokeRequest(
            reason="Scope removed",
            confirm_impact=True,
            impact_token=impact.impact_token,
        ),
        admin,
    )

    assert not UserAccountGrantDao().has_active_grant(
        user.user_id, account_set.account_set_id
    )
    assert not UserResourceGrantDao().has_active_grant(user.user_id, "DATASOURCE", "1")
    with db.session(commit=False) as session:
        persisted_resource_grant = (
            session.query(UserResourceGrantEntity)
            .filter_by(grant_id=resource_grant.grant_id)
            .one()
        )
        assert persisted_resource_grant.revoke_reason == ("ACCOUNT_SET_GRANT_REVOKED")

    restored_account = service.grant_user_account(
        user.user_id, account_set.account_set_id, admin
    )
    restored_resource = service.grant_user_resource(
        user.user_id, "DATASOURCE", "1", admin
    )
    assert restored_account.grant_id == account_grant.grant_id
    assert restored_resource.grant_id == resource_grant.grant_id


def test_agent_grant_requires_dependencies_and_move_revokes_both(service, admin):
    source_account = create_account_set(service, admin, "Account A")
    target_account = create_account_set(service, admin, "Account B")
    user = create_user(service, admin, "alice")
    service.grant_user_account(user.user_id, source_account.account_set_id, admin)
    insert_resource(
        "connect_config", 1, "db_name", "sales", source_account.account_set_id
    )
    insert_resource(
        "knowledge_space", 2, "name", "manual", source_account.account_set_id
    )
    insert_resource(
        "gpts_app", "agent-1", "app_name", "Sales Agent", source_account.account_set_id
    )
    resources = [
        {"type": "database", "value": json.dumps({"db_name": "sales"})},
        {"type": "knowledge", "value": json.dumps({"space_name": "manual"})},
    ]
    with db.session() as session:
        session.execute(
            text(
                "INSERT INTO gpts_app_detail (app_code, resources) "
                "VALUES (:app_code, :resources)"
            ),
            {"app_code": "agent-1", "resources": json.dumps(resources)},
        )

    with pytest.raises(ManagementValidationError, match="every protected"):
        service.grant_user_resource(user.user_id, "AGENT", "agent-1", admin)

    datasource_grant = service.grant_user_resource(
        user.user_id, "DATASOURCE", "1", admin
    )
    knowledge_grant = service.grant_user_resource(
        user.user_id, "KNOWLEDGE_BASE", "2", admin
    )
    agent_grant = service.grant_user_resource(user.user_id, "AGENT", "agent-1", admin)

    service.revoke_user_resource(
        user.user_id,
        knowledge_grant.grant_id,
        RevokeRequest(reason="Knowledge access removed"),
        admin,
    )
    with db.session(commit=False) as session:
        cascaded_agent = (
            session.query(UserResourceGrantEntity)
            .filter_by(grant_id=agent_grant.grant_id)
            .one()
        )
        assert cascaded_agent.is_active is False
        assert cascaded_agent.revoke_reason == "DEPENDENCY_GRANT_REVOKED"
    service.grant_user_resource(user.user_id, "KNOWLEDGE_BASE", "2", admin)
    agent_grant = service.grant_user_resource(user.user_id, "AGENT", "agent-1", admin)

    impact = service.get_resource_impact(
        "DATASOURCE", "1", target_account.account_set_id, admin
    )
    assert impact.affected_resource_grants == 1
    assert impact.affected_agent_grants == 1
    moved = service.assign_resource_account(
        "DATASOURCE",
        "1",
        AssignResourceAccountRequest(
            account_set_id=target_account.account_set_id,
            reason="Business ownership changed",
            confirm_impact=True,
            impact_token=impact.impact_token,
        ),
        admin,
    )
    assert moved.account_set_id == target_account.account_set_id
    with db.session(commit=False) as session:
        grants = {
            grant.grant_id: grant
            for grant in session.query(UserResourceGrantEntity)
            .filter(
                UserResourceGrantEntity.grant_id.in_(
                    [datasource_grant.grant_id, agent_grant.grant_id]
                )
            )
            .all()
        }
        assert grants[datasource_grant.grant_id].is_active is False
        assert grants[agent_grant.grant_id].is_active is False


def test_operations_admin_resource_scope_is_enforced(service, admin):
    first = create_account_set(service, admin, "Account A")
    second = create_account_set(service, admin, "Account B")
    operator = create_user(service, admin, "operator", role="operations_admin")
    service.grant_user_account(operator.user_id, first.account_set_id, admin)
    operator_request = UserRequest(user_id=operator.user_id, role="operations_admin")
    insert_resource("connect_config", 1, "db_name", "first", first.account_set_id)
    insert_resource("connect_config", 2, "db_name", "second", second.account_set_id)
    insert_resource("connect_config", 3, "db_name", "unowned")

    visible = service.list_managed_resources(
        1, 20, operator_request, resource_type="DATASOURCE"
    )
    assert [item.resource_id for item in visible.items] == ["1"]

    with pytest.raises(ManagementValidationError, match="within their"):
        service.get_resource_impact(
            "DATASOURCE", "1", second.account_set_id, operator_request
        )
    with pytest.raises(ManagementValidationError, match="unowned"):
        service.get_resource_impact(
            "DATASOURCE", "3", first.account_set_id, operator_request
        )

    service.grant_user_account(operator.user_id, second.account_set_id, admin)
    impact = service.get_resource_impact(
        "DATASOURCE", "1", second.account_set_id, operator_request
    )
    moved = service.assign_resource_account(
        "DATASOURCE",
        "1",
        AssignResourceAccountRequest(
            account_set_id=second.account_set_id,
            reason="Operations transfer",
            confirm_impact=True,
            impact_token=impact.impact_token,
        ),
        operator_request,
    )
    assert moved.account_set_id == second.account_set_id


def test_resource_grant_revoke_requires_reason(service, admin):
    account_set = create_account_set(service, admin, "Account A")
    user = create_user(service, admin, "alice")
    service.grant_user_account(user.user_id, account_set.account_set_id, admin)
    insert_resource("connect_config", 1, "db_name", "sales", account_set.account_set_id)
    grant = service.grant_user_resource(user.user_id, "DATASOURCE", "1", admin)

    revoked = service.revoke_user_resource(
        user.user_id,
        grant.grant_id,
        RevokeRequest(reason="No longer needed"),
        admin,
    )

    assert revoked.is_active is False
    with db.session(commit=False) as session:
        account_grant = session.query(UserAccountGrantEntity).one()
        assert account_grant.is_active is True


def test_resource_listing_paginates_across_all_resource_types(service, admin):
    account_set = create_account_set(service, admin, "Account A")
    insert_resource("connect_config", 1, "db_name", "sales", account_set.account_set_id)
    insert_resource("knowledge_space", 2, "name", "manual", account_set.account_set_id)
    insert_resource(
        "gpts_app", "agent-1", "app_name", "Assistant", account_set.account_set_id
    )

    first_page = service.list_managed_resources(1, 2, admin)
    second_page = service.list_managed_resources(2, 2, admin)

    assert first_page.total == 3
    assert len(first_page.items) == 2
    assert len(second_page.items) == 1
    assert {item.resource_type for item in [*first_page.items, *second_page.items]} == {
        "DATASOURCE",
        "KNOWLEDGE_BASE",
        "AGENT",
    }
