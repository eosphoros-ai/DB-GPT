"""Tests for idempotent usage metering and append-only audit queries."""

from datetime import datetime, timezone

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.schemas import (
    AuditEventCreate,
    AuditQueryRequest,
    TokenUsageCreate,
    TokenUsageQueryRequest,
)
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
    TokenDailyEntity,
    TokenUsageEntity,
    UserAccountGrantEntity,
)
from dbgpt_serve.auth.service.audit_service import AuditService
from dbgpt_serve.auth.service.errors import ManagementValidationError
from dbgpt_serve.auth.service.token_service import TokenService
from dbgpt_serve.utils.auth import UserRequest


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield
    db.Model.metadata.drop_all(bind=db.engine)


def usage(call_id, user_id="query-1", account_set_id="account-1", tokens=12):
    return TokenUsageCreate(
        call_id=call_id,
        request_id="request-1",
        session_id="session-1",
        user_id=user_id,
        role_snapshot="query_user",
        account_set_id=account_set_id,
        account_set_snapshot="Account A",
        entry_resource_type="DATASOURCE",
        entry_resource_id="1",
        model="gpt-test",
        input_tokens=tokens - 2,
        output_tokens=2,
        total_tokens=tokens,
        metering_source="provider",
        duration_ms=100,
        status="success",
        gmt_created=datetime(2026, 7, 16, 16, 0, tzinfo=timezone.utc),
    )


def test_record_usage_is_idempotent_and_uses_shanghai_day():
    service = TokenService()

    assert service.record_usage(usage("call-1")) is True
    assert service.record_usage(usage("call-1")) is False
    assert service.record_usage(usage("call-2", tokens=8)) is True

    with db.session(commit=False) as session:
        assert session.query(TokenUsageEntity).count() == 2
        daily = session.query(TokenDailyEntity).one()
        assert daily.stat_date == "2026-07-17"
        assert daily.input_tokens == 16
        assert daily.output_tokens == 4
        assert daily.total_tokens == 20
        assert daily.call_count == 2


def test_usage_queries_enforce_role_data_scope():
    service = TokenService()
    service.record_usage(usage("call-query", user_id="query-1"))
    service.record_usage(
        usage("call-other", user_id="query-2", account_set_id="account-2")
    )
    with db.session() as session:
        session.add_all(
            [
                AccountSetEntity(
                    account_set_id="account-1",
                    name="Account A",
                    is_active=True,
                    created_by="admin-1",
                ),
                AccountSetEntity(
                    account_set_id="account-2",
                    name="Account B",
                    is_active=True,
                    created_by="admin-1",
                ),
                UserAccountGrantEntity(
                    grant_id="grant-1",
                    user_id="operator-1",
                    account_set_id="account-1",
                    is_active=True,
                    granted_by="admin-1",
                ),
            ]
        )

    query_page = service.query_usage(
        TokenUsageQueryRequest(),
        UserRequest(user_id="query-1", role="query_user"),
        1,
        20,
    )
    operations_page = service.query_usage(
        TokenUsageQueryRequest(),
        UserRequest(user_id="operator-1", role="operations_admin"),
        1,
        20,
    )
    admin_page = service.query_usage(
        TokenUsageQueryRequest(),
        UserRequest(user_id="admin-1", role="system_admin"),
        1,
        20,
    )

    assert [item.call_id for item in query_page.items] == ["call-query"]
    assert [item.call_id for item in operations_page.items] == ["call-query"]
    assert admin_page.total == 2


def test_audit_is_append_only_scoped_and_rejects_sensitive_snapshots():
    service = AuditService()
    admin = UserRequest(user_id="admin-1", role="system_admin")
    event = service.record(
        AuditEventCreate(
            event_time=datetime(2026, 7, 17, 8, 0),
            operator_user_id="admin-1",
            operator_role_snapshot="system_admin",
            target_type="USER",
            target_id="query-1",
            action="USER.DISABLE",
            result="success",
            request_id="request-1",
            before_snapshot='{"is_active":true}',
            after_snapshot='{"is_active":false}',
        )
    )

    page = service.query(AuditQueryRequest(action="USER.DISABLE"), 1, 20, admin)
    assert page.total == 1
    assert service.get(event.event_id, admin).target_id == "query-1"
    with pytest.raises(ManagementValidationError, match="system administrator"):
        service.query(
            AuditQueryRequest(),
            1,
            20,
            UserRequest(user_id="query-1", role="query_user"),
        )
    with pytest.raises(ManagementValidationError, match="Sensitive"):
        service.record(
            AuditEventCreate(
                event_time=datetime(2026, 7, 17, 8, 0),
                target_type="USER",
                action="USER.UPDATE",
                result="success",
                after_snapshot='{"password":"forbidden"}',
            )
        )
