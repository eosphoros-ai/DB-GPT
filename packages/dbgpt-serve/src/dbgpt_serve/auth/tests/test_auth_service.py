"""Tests for password authentication and server-side sessions."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from dbgpt.storage.metadata import db
from dbgpt_serve.auth.config import ServeConfig
from dbgpt_serve.auth.models.models import (
    AuditEventEntity,
    SessionEntity,
    UserEntity,
)
from dbgpt_serve.auth.service.service import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    AuthConfigurationError,
    AuthenticationError,
    Service,
)

TEST_SECRET = "test-only-jwt-secret-with-at-least-32-bytes"


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield
    db.Model.metadata.drop_all(bind=db.engine)


@pytest.fixture
def service():
    return Service(
        None,
        ServeConfig(
            jwt_secret=TEST_SECRET,
            jwt_access_expire_minutes=30,
            jwt_absolute_expire_minutes=120,
            login_fail_lock_threshold=2,
            login_fail_lock_minutes=15,
            cookie_secure=True,
        ),
    )


def create_user(service, role="query_user", is_active=True):
    with db.session() as session:
        session.add(
            UserEntity(
                user_id="user-1",
                login_name="alice",
                display_name="Alice",
                password_hash=service.hash_password("correct-password"),
                role=role,
                is_active=is_active,
            )
        )


def test_login_creates_audited_revocable_session(service):
    create_user(service)

    token, user = service.login("alice", "correct-password", "x" * 100, "test")
    authenticated_user, session_id = service.authenticate_token(token)

    assert user.user_id == "user-1"
    assert authenticated_user.role == "query_user"
    claims = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )
    assert "role" not in claims
    with db.session(commit=False) as session:
        auth_session = session.query(SessionEntity).one()
        events = session.query(AuditEventEntity).all()
        assert auth_session.session_id == session_id
        assert auth_session.source_ip == "x" * 64
        assert [event.action for event in events] == ["AUTH.LOGIN"]
        assert events[0].result == "success"
        assert events[0].source_ip == "x" * 64

    service.logout("user-1", session_id)
    with pytest.raises(AuthenticationError):
        service.authenticate_token(token)
    with db.session(commit=False) as session:
        assert [
            event.action
            for event in session.query(AuditEventEntity)
            .order_by(AuditEventEntity.id)
            .all()
        ] == ["AUTH.LOGIN", "AUTH.LOGOUT"]


def test_login_failure_is_generic_and_locks_account(service):
    create_user(service)

    for password in ["wrong-one", "wrong-two"]:
        with pytest.raises(AuthenticationError, match="Invalid login name or password"):
            service.login("alice", password, "127.0.0.1", "test")

    with db.session(commit=False) as session:
        user = session.query(UserEntity).one()
        assert user.login_fail_count == 2
        assert user.locked_until is not None
        assert session.query(AuditEventEntity).count() == 2

    with pytest.raises(AuthenticationError, match="Invalid login name or password"):
        service.login("missing", "wrong-two", "127.0.0.1", "test")
    with pytest.raises(AuthenticationError, match="Invalid login name or password"):
        service.login("alice", "correct-password", "127.0.0.1", "test")
    with db.session(commit=False) as session:
        assert (
            session.query(AuditEventEntity)
            .order_by(AuditEventEntity.id.desc())
            .first()
            .deny_reason
            == "ACCOUNT_LOCKED"
        )


def test_authentication_reads_current_role_and_active_state(service):
    create_user(service)
    token, _ = service.login("alice", "correct-password", "", "")

    with db.session() as session:
        user = session.query(UserEntity).one()
        user.role = "operations_admin"
    authenticated_user, _ = service.authenticate_token(token)
    assert authenticated_user.role == "operations_admin"

    with db.session() as session:
        user = session.query(UserEntity).one()
        user.is_active = False
    with pytest.raises(AuthenticationError):
        service.authenticate_token(token)


def test_invalid_database_role_fails_closed(service):
    create_user(service, role="invalid_role")

    with pytest.raises(AuthenticationError, match="Invalid login name or password"):
        service.login("alice", "correct-password", "", "")
    with db.session(commit=False) as session:
        assert session.query(AuditEventEntity).one().deny_reason == "INVALID_ROLE"


def test_expired_server_session_rejects_otherwise_valid_jwt(service):
    create_user(service)
    token, _ = service.login("alice", "correct-password", "", "")

    with db.session() as session:
        auth_session = session.query(SessionEntity).one()
        auth_session.idle_expires_at = utcnow() - timedelta(seconds=1)

    with pytest.raises(AuthenticationError):
        service.authenticate_token(token)


def test_initial_admin_is_created_once(service):
    service.config.initial_admin_login = "admin"
    service.config.initial_admin_password = "initial-password"

    created = service.ensure_initial_admin()
    duplicate = service.ensure_initial_admin()

    assert created is not None
    assert created.role == "system_admin"
    assert duplicate is None
    with db.session(commit=False) as session:
        user = session.query(UserEntity).one()
        assert user.password_hash != "initial-password"
        assert service.verify_password("initial-password", user.password_hash)


def test_initial_admin_rejects_invalid_bootstrap_credentials(service):
    service.config.initial_admin_login = " "
    service.config.initial_admin_password = "initial-password"

    with pytest.raises(AuthConfigurationError, match="initial_admin_login"):
        service.ensure_initial_admin()


def test_invalid_session_or_lock_configuration_fails_closed():
    with pytest.raises(AuthConfigurationError, match="login_fail_lock_minutes"):
        Service(None, ServeConfig(login_fail_lock_minutes=0))
    with pytest.raises(AuthConfigurationError, match="cookie_secure"):
        Service(None, ServeConfig(cookie_secure="false"))


def test_auth_config_masks_secrets_when_printed():
    config = ServeConfig(
        jwt_secret="jwt-secret-that-must-not-be-printed",
        initial_admin_password="admin-password-that-must-not-be-printed",
    )

    printed_config = str(config)
    represented_config = repr(config)
    assert config.jwt_secret not in printed_config
    assert config.initial_admin_password not in printed_config
    assert config.jwt_secret not in represented_config
    assert config.initial_admin_password not in represented_config


def test_short_jwt_secret_fails_closed():
    service = Service(None, ServeConfig(jwt_secret="too-short"))

    with pytest.raises(AuthConfigurationError):
        service.login("alice", "password", "", "")


def test_bcrypt_password_length_is_enforced(service):
    with pytest.raises(ValueError, match="72 bytes"):
        service.hash_password("密" * 25)

    create_user(service)
    with pytest.raises(AuthenticationError, match="Invalid login name or password"):
        service.login("alice", "密" * 25, "", "")
