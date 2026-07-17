"""Transactional tests for authorization administration services."""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.api.schemas import (
    AccountSetCreateRequest,
    ConfirmImpactRequest,
    ImportBatchRequest,
    ImportCandidateResponse,
    UserCreateRequest,
    UserListRequest,
    UserUpdateRequest,
)
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import (
    AuditEventEntity,
    ImportBatchEntity,
    SessionEntity,
    UserAccountGrantEntity,
    UserEntity,
    UserResourceGrantEntity,
)
from dbgpt_serve.auth.service.errors import (
    ImpactConfirmationRequiredError,
    ImportSourceError,
    ManagementConflictError,
)
from dbgpt_serve.auth.service.importer import LszyzdImporter
from dbgpt_serve.auth.service.service import AuthenticationError, Service
from dbgpt_serve.utils.auth import UserRequest

TEST_SECRET = "test-only-jwt-secret-with-at-least-32-bytes"


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FakeImporter:
    source_name = "erp-directory"

    def __init__(self):
        self.candidates = [
            ImportCandidateResponse(
                employee_no="E001",
                name="Imported Alice",
                is_enabled=True,
                category="sales",
                position="manager",
                team="A",
                role_label="query",
            ),
            ImportCandidateResponse(employee_no="E002", name="Imported Bob"),
        ]

    def preview(self, limit=100):
        return self.candidates[:limit]


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
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
def importer():
    return FakeImporter()


@pytest.fixture
def service(importer):
    return Service(
        None,
        ServeConfig(jwt_secret=TEST_SECRET),
        importer=importer,
    )


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


def create_account_set(service, admin, name="Account A"):
    return service.create_account_set(AccountSetCreateRequest(name=name), admin)


def create_query_user(service, admin, account_set_id=None, login_name="alice"):
    return service.create_user(
        UserCreateRequest(
            login_name=login_name,
            display_name="Alice",
            role="query_user",
            initial_password="correct-password",
            initial_account_set_ids=[account_set_id] if account_set_id else [],
        ),
        admin,
    )


def test_create_list_and_audit_user_without_exposing_password(service, admin):
    account_set = create_account_set(service, admin)
    user = create_query_user(service, admin, account_set.account_set_id)

    page = service.list_users(
        filters=UserListRequest(login_name_like="ali"),
        page=1,
        page_size=20,
        operator=admin,
    )

    assert page.total == 1
    assert any(item.user_id == user.user_id for item in page.items)
    with db.session(commit=False) as session:
        entity = session.query(UserEntity).filter_by(user_id=user.user_id).one()
        grant = (
            session.query(UserAccountGrantEntity).filter_by(user_id=user.user_id).one()
        )
        event_entity = (
            session.query(AuditEventEntity)
            .filter_by(action="USER.CREATE", target_id=user.user_id)
            .one()
        )
        assert entity.password_hash != "correct-password"
        assert service.verify_password("correct-password", entity.password_hash)
        assert grant.account_set_id == account_set.account_set_id
        assert "password" not in (event_entity.after_snapshot or "").lower()

    with pytest.raises(ManagementConflictError):
        create_query_user(service, admin, login_name="alice")


def test_role_change_requires_confirmation_and_revokes_scope(service, admin):
    account_set = create_account_set(service, admin)
    user = create_query_user(service, admin, account_set.account_set_id)
    now = utcnow()
    with db.session() as session:
        session.add(
            UserResourceGrantEntity(
                grant_id="resource-grant-1",
                user_id=user.user_id,
                resource_type="DATASOURCE",
                resource_id="datasource-1",
                account_set_id=account_set.account_set_id,
                is_active=True,
                granted_by=admin.user_id,
                gmt_created=now,
                gmt_modified=now,
            )
        )

    with pytest.raises(ImpactConfirmationRequiredError):
        service.update_user(
            user.user_id,
            UserUpdateRequest(role="operations_admin"),
            admin,
        )

    updated = service.update_user(
        user.user_id,
        UserUpdateRequest(
            role="operations_admin",
            change_reason="Changed job responsibilities",
            confirm_role_change=True,
        ),
        admin,
    )
    assert updated.role == "operations_admin"
    with db.session(commit=False) as session:
        resource_grant = session.query(UserResourceGrantEntity).one()
        account_grant = session.query(UserAccountGrantEntity).one()
        assert resource_grant.is_active is False
        assert resource_grant.revoke_reason == "ROLE_CHANGED"
        assert account_grant.is_active is True

    service.update_user(
        user.user_id,
        UserUpdateRequest(
            role="system_admin",
            change_reason="Emergency administrator assignment",
            confirm_role_change=True,
        ),
        admin,
    )
    with db.session(commit=False) as session:
        assert session.query(UserAccountGrantEntity).one().is_active is False


def test_last_active_system_admin_cannot_be_disabled_or_demoted(service, admin):
    with pytest.raises(ManagementConflictError, match="last active"):
        service.toggle_user_active(admin.user_id, False, admin)

    with pytest.raises(ManagementConflictError, match="last active"):
        service.update_user(
            admin.user_id,
            UserUpdateRequest(
                role="query_user",
                change_reason="Invalid last-admin change",
                confirm_role_change=True,
            ),
            admin,
        )


def test_disabling_and_password_reset_revoke_sessions(service, admin):
    user = create_query_user(service, admin)
    token, _ = service.login("alice", "correct-password", "", "")

    service.toggle_user_active(user.user_id, False, admin)
    with db.session(commit=False) as session:
        auth_session = session.query(SessionEntity).one()
        assert auth_session.revoked_at is not None
        assert auth_session.revoke_reason == "USER_DISABLED"

    service.toggle_user_active(user.user_id, True, admin)
    service.set_password(user.user_id, "new-password", admin)
    with pytest.raises(AuthenticationError):
        service.authenticate_token(token)
    service.login("alice", "new-password", "", "")


def test_account_set_deactivation_requires_current_impact(service, admin):
    account_set = create_account_set(service, admin)
    create_query_user(service, admin, account_set.account_set_id)
    with db.session() as session:
        for table_name in ("connect_config", "knowledge_space", "gpts_app"):
            session.execute(
                text(
                    f"INSERT INTO {table_name} (account_set_id) "
                    "VALUES (:account_set_id)"
                ),
                {"account_set_id": account_set.account_set_id},
            )
    impact = service.get_account_set_impact(account_set.account_set_id, admin)

    assert impact.user_grant_count == 1
    assert impact.resource_count == 3
    with pytest.raises(ImpactConfirmationRequiredError):
        service.toggle_account_set_active(
            account_set.account_set_id, False, admin, None
        )

    deactivated = service.toggle_account_set_active(
        account_set.account_set_id,
        False,
        admin,
        ConfirmImpactRequest(
            reason="Account set retired",
            confirm_impact=True,
            impact_token=impact.impact_token,
        ),
    )
    assert deactivated.is_active is False


def test_import_is_one_time_password_free_and_does_not_sync(service, admin, importer):
    request = ImportBatchRequest(
        users=[
            {
                "employee_no": "E001",
                "login_name": "imported-alice",
                "role": "query_user",
                "initial_password": "import-password",
            }
        ]
    )

    first = service.create_from_import(request, admin)
    importer.candidates[0] = ImportCandidateResponse(
        employee_no="E001", name="Externally Renamed"
    )
    second = service.create_from_import(request, admin)

    assert first.created_count == 1
    assert second.created_count == 0
    assert second.skipped_count == 1
    assert second.result_summary[0]["reason"] == "SOURCE_RECORD_ALREADY_IMPORTED"
    with db.session(commit=False) as session:
        user = session.query(UserEntity).filter_by(login_name="imported-alice").one()
        batches = session.query(ImportBatchEntity).all()
        serialized = "".join(
            (batch.selected_summary or "") + (batch.result_summary or "")
            for batch in batches
        )
        assert user.display_name == "Imported Alice"
        assert "import-password" not in serialized
        assert "password" not in serialized.lower()


def test_skipped_source_record_can_be_imported_when_it_appears(
    service, admin, importer
):
    request = ImportBatchRequest(
        users=[
            {
                "employee_no": "E003",
                "login_name": "late-user",
                "role": "query_user",
                "initial_password": "import-password",
            }
        ]
    )

    missing = service.create_from_import(request, admin)
    importer.candidates.append(
        ImportCandidateResponse(employee_no="E003", name="Late User")
    )
    created = service.create_from_import(request, admin)

    assert missing.result_summary[0]["reason"] == "SOURCE_RECORD_MISSING"
    assert created.created_count == 1


class RecordingConnector:
    def __init__(self):
        self.engine = create_engine("sqlite:///:memory:")
        self._session_factory = sessionmaker(bind=self.engine)
        self.statements = []
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE LSZYZD ("
                    "LSZYZD_BH TEXT, LSZYZD_MC TEXT, LSZYZD_YXBZ INTEGER, "
                    "LSZYZD_LBBH TEXT, LSZYZD_ZW TEXT, LSZYZD_BANZU TEXT, "
                    "LSZYZD_ROLE TEXT, LSZYZD_PWD TEXT)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO LSZYZD VALUES "
                    "('E001', 'Alice', 1, 'sales', 'manager', 'A', 'query', "
                    "'forbidden-password')"
                )
            )
        event.listen(self.engine, "before_cursor_execute", self._record_statement)

    def _record_statement(
        self, connection, cursor, statement, parameters, context, executemany
    ):
        self.statements.append(statement)

    def get_table_names(self):
        return ["LSZYZD"]

    def get_columns(self, table_name):
        return [
            {"name": name}
            for name in (
                "LSZYZD_BH",
                "LSZYZD_MC",
                "LSZYZD_YXBZ",
                "LSZYZD_LBBH",
                "LSZYZD_ZW",
                "LSZYZD_BANZU",
                "LSZYZD_ROLE",
                "LSZYZD_PWD",
            )
        ]

    @contextmanager
    def session_scope(self, commit=False):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()


class RecordingConnectorManager:
    def __init__(self, connector):
        self.connector = connector

    def get_connector(self, datasource_name):
        assert datasource_name == "erp-directory"
        return self.connector


def test_lszyzd_importer_selects_only_allowed_fields():
    connector = RecordingConnector()
    importer = LszyzdImporter(
        RecordingConnectorManager(connector), datasource_name="erp-directory"
    )

    candidates = importer.preview()
    select_sql = next(
        statement for statement in connector.statements if "SELECT" in statement.upper()
    )

    assert candidates[0].employee_no == "E001"
    assert candidates[0].name == "Alice"
    assert "LSZYZD_PWD" not in select_sql.upper()
    assert "LSZYZD_BH" in select_sql.upper()


def test_lszyzd_importer_requires_business_number_and_name():
    connector = RecordingConnector()
    connector.get_columns = lambda table_name: [{"name": "LSZYZD_MC"}]
    importer = LszyzdImporter(
        RecordingConnectorManager(connector), datasource_name="erp-directory"
    )

    with pytest.raises(ImportSourceError, match="missing required fields"):
        importer.preview()
