"""Tests for authorization-center persistence models."""

import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
    AuditEventDao,
    AuditEventEntity,
    ImportBatchEntity,
    SessionDao,
    SessionEntity,
    TokenDailyEntity,
    TokenUsageEntity,
    UserAccountGrantDao,
    UserAccountGrantEntity,
    UserDao,
    UserEntity,
    UserResourceGrantDao,
    UserResourceGrantEntity,
)

AUTH_TABLE_COLUMNS = {
    "dbgpt_auth_user": {
        "id",
        "user_id",
        "login_name",
        "display_name",
        "password_hash",
        "role",
        "is_active",
        "activation_token",
        "activation_token_exp",
        "reset_token",
        "reset_token_exp",
        "login_fail_count",
        "locked_until",
        "created_by",
        "disabled_by",
        "disabled_at",
        "gmt_created",
        "gmt_modified",
    },
    "dbgpt_auth_account_set": {
        "id",
        "account_set_id",
        "name",
        "description",
        "is_active",
        "created_by",
        "gmt_created",
        "gmt_modified",
    },
    "dbgpt_auth_user_account_grant": {
        "id",
        "grant_id",
        "user_id",
        "account_set_id",
        "is_active",
        "granted_by",
        "revoked_by",
        "revoked_at",
        "revoke_reason",
        "gmt_created",
        "gmt_modified",
    },
    "dbgpt_auth_user_resource_grant": {
        "id",
        "grant_id",
        "user_id",
        "resource_type",
        "resource_id",
        "account_set_id",
        "is_active",
        "granted_by",
        "revoked_by",
        "revoked_at",
        "revoke_reason",
        "gmt_created",
        "gmt_modified",
    },
    "dbgpt_auth_import_batch": {
        "id",
        "batch_id",
        "operator_user_id",
        "source_name",
        "selected_count",
        "created_count",
        "skipped_count",
        "selected_summary",
        "result_summary",
        "gmt_created",
    },
    "dbgpt_auth_token_usage": {
        "id",
        "call_id",
        "request_id",
        "session_id",
        "user_id",
        "role_snapshot",
        "account_set_id",
        "account_set_snapshot",
        "entry_resource_type",
        "entry_resource_id",
        "agent_id",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "metering_source",
        "duration_ms",
        "status",
        "error_type",
        "gmt_created",
    },
    "dbgpt_auth_token_daily": {
        "id",
        "stat_date",
        "user_id",
        "role_snapshot",
        "account_set_id",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "call_count",
        "gmt_created",
        "gmt_modified",
    },
    "dbgpt_auth_audit_event": {
        "id",
        "event_id",
        "event_time",
        "operator_user_id",
        "operator_role_snapshot",
        "target_account_set_id",
        "target_type",
        "target_id",
        "action",
        "result",
        "source_ip",
        "user_agent",
        "request_id",
        "before_snapshot",
        "after_snapshot",
        "deny_reason",
    },
    "dbgpt_auth_session": {
        "id",
        "session_id",
        "user_id",
        "issued_at",
        "last_seen_at",
        "idle_expires_at",
        "absolute_expires_at",
        "revoked_at",
        "revoked_by",
        "revoke_reason",
        "source_ip",
        "user_agent",
        "gmt_created",
        "gmt_modified",
    },
}


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield
    db.Model.metadata.drop_all(bind=db.engine)


def test_auth_tables_match_design():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    assert AUTH_TABLE_COLUMNS.keys() <= table_names
    for table_name, expected_columns in AUTH_TABLE_COLUMNS.items():
        actual_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        assert actual_columns == expected_columns


@pytest.mark.parametrize(
    ("relative_path", "entity_name", "expected_index"),
    [
        (
            "datasource/manages/connect_config_db.py",
            "ConnectConfigEntity",
            "idx_connect_account_set",
        ),
        ("rag/models/models.py", "KnowledgeSpaceEntity", "idx_ks_account_set"),
        ("agent/db/gpts_app.py", "GptsAppEntity", "idx_app_account_set"),
    ],
)
def test_resource_models_have_account_set_scope_without_runtime_imports(
    relative_path, entity_name, expected_index
):
    source_path = Path(__file__).parents[2] / relative_path
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    entity = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == entity_name
    )
    account_set_assignment = next(
        node
        for node in entity.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "account_set_id"
    )
    column_call = account_set_assignment.value
    assert isinstance(column_call, ast.Call)
    assert isinstance(column_call.func, ast.Name)
    assert column_call.func.id == "Column"
    string_type = column_call.args[0]
    assert isinstance(string_type, ast.Call)
    assert isinstance(string_type.func, ast.Name)
    assert string_type.func.id == "String"
    assert isinstance(string_type.args[0], ast.Constant)
    assert string_type.args[0].value == 128
    nullable = next(
        keyword.value for keyword in column_call.keywords if keyword.arg == "nullable"
    )
    assert isinstance(nullable, ast.Constant)
    assert nullable.value is True

    index_names = {
        argument.value
        for node in ast.walk(entity)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Index"
        for argument in node.args[:1]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    }

    assert expected_index in index_names


def test_migration_registry_imports_all_authorization_entities():
    repository_root = Path(__file__).parents[6]
    registry_path = (
        repository_root
        / "packages"
        / "dbgpt-app"
        / "src"
        / "dbgpt_app"
        / "initialization"
        / "db_model_initialization.py"
    )
    module = ast.parse(registry_path.read_text(encoding="utf-8"))
    registry_assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_MODELS"
            for target in node.targets
        )
    )
    assert isinstance(registry_assignment.value, ast.List)
    registered_names = {
        item.id for item in registry_assignment.value.elts if isinstance(item, ast.Name)
    }

    assert {
        "UserEntity",
        "AccountSetEntity",
        "UserAccountGrantEntity",
        "UserResourceGrantEntity",
        "ImportBatchEntity",
        "TokenUsageEntity",
        "TokenDailyEntity",
        "AuditEventEntity",
        "SessionEntity",
        "GptsAppEntity",
    } <= registered_names


def test_user_unique_constraints_and_defaults():
    with db.session() as session:
        session.add(
            UserEntity(
                user_id="user-1",
                login_name="alice",
                display_name="Alice",
                password_hash="not-a-real-hash",
                role="query_user",
            )
        )

    user = UserDao().get_by_login_name("alice")
    assert user is not None
    assert user.is_active is True
    assert user.login_fail_count == 0
    assert user.gmt_created is not None
    assert UserDao().count_active_admins() == 0

    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(
                UserEntity(
                    user_id="user-2",
                    login_name="alice",
                    display_name="Other Alice",
                    password_hash="not-a-real-hash",
                    role="query_user",
                )
            )


def test_grant_dao_checks_only_active_grants():
    with db.session() as session:
        session.add_all(
            [
                UserAccountGrantEntity(
                    grant_id="account-grant-1",
                    user_id="user-1",
                    account_set_id="account-set-1",
                    granted_by="admin-1",
                ),
                UserResourceGrantEntity(
                    grant_id="resource-grant-1",
                    user_id="user-1",
                    resource_type="DATASOURCE",
                    resource_id="datasource-1",
                    account_set_id="account-set-1",
                    granted_by="admin-1",
                ),
            ]
        )

    assert UserAccountGrantDao().has_active_grant("user-1", "account-set-1")
    assert UserResourceGrantDao().has_active_grant(
        "user-1", "DATASOURCE", "datasource-1"
    )
    assert not UserResourceGrantDao().has_active_grant(
        "user-1", "KNOWLEDGE_BASE", "datasource-1"
    )


def test_daily_usage_dimensions_are_unique_for_pure_chat():
    assert TokenUsageEntity.__table__.c.account_set_id.nullable is True
    assert TokenDailyEntity.__table__.c.account_set_id.nullable is False

    daily = {
        "stat_date": "2026-07-17",
        "user_id": "user-1",
        "role_snapshot": "query_user",
        "account_set_id": "",
        "model": "test-model",
    }
    with db.session() as session:
        session.add(TokenDailyEntity(**daily))

    with pytest.raises(IntegrityError):
        with db.session() as session:
            session.add(TokenDailyEntity(**daily))

    with db.session() as session:
        session.add(TokenDailyEntity(**{**daily, "role_snapshot": "operations_admin"}))


def test_session_dao_rejects_expired_and_revoked_sessions():
    now = datetime.now()
    with db.session() as session:
        session.add_all(
            [
                SessionEntity(
                    session_id="active-session",
                    user_id="user-1",
                    idle_expires_at=now + timedelta(minutes=30),
                    absolute_expires_at=now + timedelta(hours=8),
                ),
                SessionEntity(
                    session_id="expired-session",
                    user_id="user-1",
                    idle_expires_at=now - timedelta(minutes=1),
                    absolute_expires_at=now + timedelta(hours=8),
                ),
                SessionEntity(
                    session_id="revoked-session",
                    user_id="user-1",
                    idle_expires_at=now + timedelta(minutes=30),
                    absolute_expires_at=now + timedelta(hours=8),
                    revoked_at=now,
                ),
            ]
        )

    dao = SessionDao()
    assert dao.get_active_session("active-session", "user-1", now) is not None
    assert dao.get_active_session("expired-session", "user-1", now) is None
    assert dao.get_active_session("revoked-session", "user-1", now) is None


def test_audit_dao_is_append_only():
    dao = AuditEventDao()
    event = dao.append(
        {
            "event_id": "event-1",
            "target_type": "SYSTEM",
            "action": "MIGRATION.VERIFY",
            "result": "success",
        }
    )

    result = dao.query({"target_type": "SYSTEM"}, page=1, page_size=20)
    assert event.id is not None
    assert result.total_count == 1
    assert result.items[0].event_id == "event-1"

    with pytest.raises(TypeError, match="append-only"):
        dao.delete({"event_id": "event-1"})
    with pytest.raises(TypeError, match="append-only"):
        dao.update({"event_id": "event-1"}, {"result": "error"})


def test_all_entity_classes_are_registered():
    expected_entities = {
        UserEntity,
        AccountSetEntity,
        UserAccountGrantEntity,
        UserResourceGrantEntity,
        ImportBatchEntity,
        TokenUsageEntity,
        TokenDailyEntity,
        AuditEventEntity,
        SessionEntity,
    }

    assert {entity.__table__.name for entity in expected_entities} == set(
        AUTH_TABLE_COLUMNS
    )
