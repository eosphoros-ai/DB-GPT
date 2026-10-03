from datetime import datetime

import pytest

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.access import (
    DashboardAuthorizationService,
    DashboardDataSourcePolicy,
)
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardAccessDao,
    DashboardAccessDeniedError,
    DashboardAuditDao,
    DashboardDao,
    DashboardEntity,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAction,
    DashboardRole,
)


class EnvironmentPolicy:
    """Importable fixture used to verify deployment-owned policy loading."""

    def can_query(self, actor_id: str, data_source_id: str) -> bool:
        return actor_id == "bob" and data_source_id == "sales"


@pytest.fixture
def authorization():
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    dashboard_dao = DashboardDao(manager)
    dashboard_dao.create_dashboard(
        DashboardEntity(
            id="dashboard-rbac",
            owner_id="alice",
            title="RBAC",
            description="",
            data_source_id="sales",
            schema_json='{"schema_version":"1.0"}',
            current_revision=1,
            status="draft",
            gmt_created=datetime.now(),
            gmt_modified=datetime.now(),
        ),
        ensure_owner_member=True,
    )
    return DashboardAuthorizationService(
        dashboard_dao=dashboard_dao,
        access_dao=DashboardAccessDao(manager),
        audit_dao=DashboardAuditDao(manager),
    )


def test_role_matrix_is_deny_by_default(authorization):
    authorization.upsert_member("dashboard-rbac", "alice", "bob", DashboardRole.EDITOR)
    authorization.upsert_member(
        "dashboard-rbac", "alice", "carol", DashboardRole.VIEWER
    )

    for action in (DashboardAction.VIEW, DashboardAction.EDIT, DashboardAction.QUERY):
        authorization.require("dashboard-rbac", "bob", action)
    with pytest.raises(DashboardAccessDeniedError):
        authorization.require("dashboard-rbac", "bob", DashboardAction.PUBLISH)

    authorization.require("dashboard-rbac", "carol", DashboardAction.VIEW)
    with pytest.raises(DashboardAccessDeniedError):
        authorization.require("dashboard-rbac", "carol", DashboardAction.QUERY)
    with pytest.raises(DashboardAccessDeniedError):
        authorization.require("dashboard-rbac", "mallory", DashboardAction.VIEW)


def test_owner_invariant_and_accessible_list(authorization):
    authorization.upsert_member("dashboard-rbac", "alice", "bob", DashboardRole.EDITOR)
    assert [item.id for item in authorization.list_accessible("bob")] == [
        "dashboard-rbac"
    ]
    with pytest.raises(ValueError, match="owner cannot be downgraded"):
        authorization.upsert_member(
            "dashboard-rbac", "alice", "alice", DashboardRole.VIEWER
        )
    with pytest.raises(ValueError, match="owner cannot be removed"):
        authorization.remove_member("dashboard-rbac", "alice", "alice")


def test_query_permission_can_require_external_data_source_policy(authorization):
    authorization.upsert_member("dashboard-rbac", "alice", "bob", DashboardRole.EDITOR)
    authorization._data_source_authorizer = lambda actor_id, source_id: (
        actor_id == "bob" and source_id == "allowed"
    )
    authorization.require(
        "dashboard-rbac",
        "bob",
        DashboardAction.QUERY,
        data_source_ids=["allowed"],
    )
    with pytest.raises(DashboardAccessDeniedError, match="cannot query data source"):
        authorization.require(
            "dashboard-rbac",
            "bob",
            DashboardAction.QUERY,
            data_source_ids=["blocked"],
        )


def test_query_permission_accepts_typed_platform_policy(authorization):
    class SalesPolicy:
        def can_query(self, actor_id: str, data_source_id: str) -> bool:
            return actor_id == "bob" and data_source_id == "sales"

    policy: DashboardDataSourcePolicy = SalesPolicy()
    secured = DashboardAuthorizationService(
        dashboard_dao=authorization.dashboard_dao,
        access_dao=authorization.access_dao,
        audit_dao=authorization.audit_dao,
        data_source_policy=policy,
        require_data_source_authorizer=True,
    )
    secured.upsert_member("dashboard-rbac", "alice", "bob", DashboardRole.EDITOR)
    secured.require(
        "dashboard-rbac",
        "bob",
        DashboardAction.QUERY,
        data_source_ids=["sales"],
    )
    with pytest.raises(DashboardAccessDeniedError):
        secured.require(
            "dashboard-rbac",
            "bob",
            DashboardAction.QUERY,
            data_source_ids=["payroll"],
        )


def test_data_source_policy_can_be_checked_before_a_dashboard_exists(authorization):
    class SalesPolicy:
        def can_query(self, actor_id: str, data_source_id: str) -> bool:
            return actor_id == "alice" and data_source_id == "sales"

    secured = DashboardAuthorizationService(
        dashboard_dao=authorization.dashboard_dao,
        access_dao=authorization.access_dao,
        audit_dao=authorization.audit_dao,
        data_source_policy=SalesPolicy(),
        require_data_source_authorizer=True,
    )

    secured.require_data_sources("alice", ["sales", "sales"])
    with pytest.raises(DashboardAccessDeniedError, match="cannot query data source"):
        secured.require_data_sources("alice", ["sales", "payroll"])


def test_strict_query_mode_fails_closed_without_platform_policy(authorization):
    authorization.upsert_member("dashboard-rbac", "alice", "bob", DashboardRole.EDITOR)
    authorization._require_data_source_authorizer = True

    with pytest.raises(DashboardAccessDeniedError, match="no platform policy"):
        authorization.require(
            "dashboard-rbac",
            "bob",
            DashboardAction.QUERY,
            data_source_ids=["sales"],
        )


def test_strict_query_mode_can_be_enabled_from_environment(authorization, monkeypatch):
    monkeypatch.setenv("DBGPT_DASHBOARD_REQUIRE_DATA_SOURCE_AUTHORIZATION", "1")
    strict = DashboardAuthorizationService(
        dashboard_dao=authorization.dashboard_dao,
        access_dao=authorization.access_dao,
        audit_dao=authorization.audit_dao,
    )

    assert strict._require_data_source_authorizer is True


def test_data_source_policy_can_be_loaded_from_environment(authorization, monkeypatch):
    monkeypatch.setenv(
        "DBGPT_DASHBOARD_DATA_SOURCE_POLICY", f"{__name__}.EnvironmentPolicy"
    )
    secured = DashboardAuthorizationService(
        dashboard_dao=authorization.dashboard_dao,
        access_dao=authorization.access_dao,
        audit_dao=authorization.audit_dao,
        require_data_source_authorizer=True,
    )
    secured.upsert_member("dashboard-rbac", "alice", "bob", DashboardRole.EDITOR)

    secured.require(
        "dashboard-rbac",
        "bob",
        DashboardAction.QUERY,
        data_source_ids=["sales"],
    )
    with pytest.raises(DashboardAccessDeniedError):
        secured.require(
            "dashboard-rbac",
            "bob",
            DashboardAction.QUERY,
            data_source_ids=["payroll"],
        )


def test_audit_redacts_sql_parameters_and_tokens(authorization):
    authorization.audit(
        "dashboard-rbac",
        "alice",
        "query.tested",
        details={
            "sql": "SELECT * FROM payroll",
            "parameters": {"employee": "secret-name"},
            "share_token": "secret-token",
            "row_count": 3,
        },
    )
    events = authorization.list_audit("dashboard-rbac", "alice")
    event = next(item for item in events if item.action == "query.tested")
    assert event.details == {
        "sql": "[redacted]",
        "parameters": "[redacted]",
        "share_token": "[redacted]",
        "row_count": 3,
    }
