"""Core authentication service."""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.storage.metadata import BaseDao
from dbgpt_serve.auth.api.schemas import UserResponse
from dbgpt_serve.auth.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.auth.constants import FIXED_ROLES
from dbgpt_serve.auth.models.models import (
    AuditEventEntity,
    SessionDao,
    SessionEntity,
    UserDao,
    UserEntity,
)
from dbgpt_serve.auth.service.authorization import AuthorizationMixin
from dbgpt_serve.auth.service.importer import LszyzdImporter
from dbgpt_serve.auth.service.management import ManagementMixin
from dbgpt_serve.core import BaseService

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "dbgpt-admin"
JWT_ISSUER = "dbgpt"
GENERIC_LOGIN_ERROR = "Invalid login name or password"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthenticationError(Exception):
    """Raised when credentials or session state are invalid."""


class AuthConfigurationError(RuntimeError):
    """Raised when authentication cannot operate securely."""


class Service(
    AuthorizationMixin,
    ManagementMixin,
    BaseService[UserEntity, object, UserResponse],
):
    """Password authentication and revocable session management."""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: Optional[SystemApp],
        config: ServeConfig,
        user_dao: Optional[UserDao] = None,
        session_dao: Optional[SessionDao] = None,
        importer: Optional[LszyzdImporter] = None,
    ) -> None:
        super().__init__(system_app)
        self._config = config
        self._validate_config()
        self._dao = user_dao or UserDao()
        self._session_dao = session_dao or SessionDao()
        self._importer = importer
        self._dummy_password = secrets.token_urlsafe(32)
        self._dummy_password_hash = self.hash_password(self._dummy_password)

    @property
    def dao(self) -> BaseDao:
        return self._dao

    @property
    def config(self) -> ServeConfig:
        return self._config

    def hash_password(self, password: str) -> str:
        """Hash a password using the configured adaptive password scheme."""
        if not password:
            raise ValueError("Password must not be empty")
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("ascii")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a supported plaintext password against a bcrypt hash."""
        if not password or len(password.encode("utf-8")) > 72:
            return False
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("ascii")
            )
        except (TypeError, ValueError, UnicodeError):
            return False

    def login(
        self, login_name: str, password: str, ip: str, user_agent: str
    ) -> tuple[str, UserResponse]:
        """Authenticate credentials and create a revocable session."""
        self._require_jwt_secret()
        ip = (ip or "")[:64]
        user_agent = (user_agent or "")[:512]
        now = _utcnow()
        session_id = str(uuid.uuid4())
        absolute_expires_at = now + timedelta(
            minutes=self._config.jwt_absolute_expire_minutes
        )
        idle_expires_at = min(
            now + timedelta(minutes=self._config.jwt_access_expire_minutes),
            absolute_expires_at,
        )
        login_error: Optional[AuthenticationError] = None
        user_response: Optional[UserResponse] = None

        with self._dao.session() as session:
            user = (
                session.query(UserEntity)
                .filter(UserEntity.login_name == login_name)
                .with_for_update()
                .first()
            )
            password_is_supported = 0 < len(password.encode("utf-8")) <= 72
            candidate_hash = user.password_hash if user else self._dummy_password_hash
            candidate_password = (
                password if password_is_supported else self._dummy_password
            )
            password_matches = self.verify_password(candidate_password, candidate_hash)
            password_matches = password_matches and password_is_supported

            is_locked = bool(user and user.locked_until and user.locked_until > now)
            is_allowed = bool(
                user
                and user.is_active
                and user.role in FIXED_ROLES
                and not is_locked
                and password_matches
            )
            if not is_allowed:
                if user and user.is_active and not is_locked and not password_matches:
                    user.login_fail_count += 1
                    if user.login_fail_count >= self._config.login_fail_lock_threshold:
                        user.locked_until = now + timedelta(
                            minutes=self._config.login_fail_lock_minutes
                        )
                if is_locked:
                    deny_reason = "ACCOUNT_LOCKED"
                elif user and not user.is_active:
                    deny_reason = "ACCOUNT_DISABLED"
                elif user and user.role not in FIXED_ROLES:
                    deny_reason = "INVALID_ROLE"
                else:
                    deny_reason = "INVALID_CREDENTIALS"
                session.add(
                    self._audit_event(
                        action="AUTH.LOGIN",
                        result="denied",
                        operator_user_id=user.user_id if user else None,
                        operator_role=user.role if user else None,
                        target_id=user.user_id if user else None,
                        source_ip=ip,
                        user_agent=user_agent,
                        deny_reason=deny_reason,
                    )
                )
                login_error = AuthenticationError(GENERIC_LOGIN_ERROR)
            else:
                user.login_fail_count = 0
                user.locked_until = None
                session.add(
                    SessionEntity(
                        session_id=session_id,
                        user_id=user.user_id,
                        issued_at=now,
                        last_seen_at=now,
                        idle_expires_at=idle_expires_at,
                        absolute_expires_at=absolute_expires_at,
                        source_ip=ip or None,
                        user_agent=(user_agent or "")[:512] or None,
                    )
                )
                session.add(
                    self._audit_event(
                        action="AUTH.LOGIN",
                        result="success",
                        operator_user_id=user.user_id,
                        operator_role=user.role,
                        target_id=user.user_id,
                        source_ip=ip,
                        user_agent=user_agent,
                    )
                )
                user_response = UserResponse.from_entity(user)

        if login_error:
            raise login_error
        if user_response is None:
            raise AuthenticationError(GENERIC_LOGIN_ERROR)

        token = jwt.encode(
            {
                "sub": user_response.user_id,
                "jti": session_id,
                "iat": now,
                "exp": absolute_expires_at,
                "iss": JWT_ISSUER,
                "aud": JWT_AUDIENCE,
            },
            self._config.jwt_secret,
            algorithm=JWT_ALGORITHM,
        )
        return token, user_response

    def authenticate_token(self, token: str) -> tuple[UserResponse, str]:
        """Validate a JWT, its server-side session, and current user state."""
        self._require_jwt_secret()
        try:
            payload = jwt.decode(
                token,
                self._config.jwt_secret,
                algorithms=[JWT_ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
            )
        except JWTError as exc:
            raise AuthenticationError("Invalid or expired session") from exc

        user_id = payload.get("sub")
        session_id = payload.get("jti")
        if not isinstance(user_id, str) or not isinstance(session_id, str):
            raise AuthenticationError("Invalid or expired session")

        now = _utcnow()
        with self._session_dao.session() as session:
            auth_session = (
                session.query(SessionEntity)
                .filter(
                    SessionEntity.session_id == session_id,
                    SessionEntity.user_id == user_id,
                    SessionEntity.revoked_at.is_(None),
                    SessionEntity.idle_expires_at > now,
                    SessionEntity.absolute_expires_at > now,
                )
                .first()
            )
            user = (
                session.query(UserEntity)
                .filter(UserEntity.user_id == user_id, UserEntity.is_active.is_(True))
                .first()
            )
            if auth_session is None or user is None or user.role not in FIXED_ROLES:
                raise AuthenticationError("Invalid or expired session")

            auth_session.last_seen_at = now
            auth_session.idle_expires_at = min(
                now + timedelta(minutes=self._config.jwt_access_expire_minutes),
                auth_session.absolute_expires_at,
            )
            user_response = UserResponse.from_entity(user)

        return user_response, session_id

    def csrf_token(self, token: str) -> str:
        """Derive a CSRF token without exposing the session cookie value."""
        self._require_jwt_secret()
        return hmac.new(
            self._config.jwt_secret.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def validate_csrf_token(self, token: str, candidate: str) -> bool:
        """Compare a submitted CSRF token using constant-time equality."""
        if not candidate:
            return False
        return hmac.compare_digest(self.csrf_token(token), candidate)

    def logout(self, user_id: str, session_id: str) -> None:
        """Idempotently revoke the current authenticated session."""
        now = _utcnow()
        with self._session_dao.session() as session:
            auth_session = (
                session.query(SessionEntity)
                .filter(
                    SessionEntity.session_id == session_id,
                    SessionEntity.user_id == user_id,
                )
                .first()
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = now
                auth_session.revoked_by = user_id
                auth_session.revoke_reason = "LOGOUT"
            user = (
                session.query(UserEntity).filter(UserEntity.user_id == user_id).first()
            )
            session.add(
                self._audit_event(
                    action="AUTH.LOGOUT",
                    result="success",
                    operator_user_id=user_id,
                    operator_role=user.role if user else None,
                    target_type="SESSION",
                    target_id=session_id,
                )
            )

    def get_user(self, user_id: str) -> UserResponse:
        """Return the current non-sensitive user representation."""
        user = self._dao.get_by_user_id(user_id)
        if user is None or not user.is_active or user.role not in FIXED_ROLES:
            raise AuthenticationError("User is not active")
        return UserResponse.from_entity(user)

    def ensure_initial_admin(self) -> Optional[UserResponse]:
        """Create the configured first administrator when no active admin exists."""
        if self._dao.count_active_admins() > 0:
            return None
        if not isinstance(self._config.initial_admin_password, str):
            raise AuthConfigurationError(
                "dbgpt.serve.auth.initial_admin_password must be a string"
            )
        if not self._config.initial_admin_password:
            logger.warning(
                "No initial administrator exists and initial_admin_password is empty"
            )
            return None

        if not isinstance(self._config.initial_admin_login, str):
            raise AuthConfigurationError(
                "dbgpt.serve.auth.initial_admin_login must be a string"
            )
        login_name = self._config.initial_admin_login.strip()
        if not login_name or len(login_name) > 128:
            raise AuthConfigurationError(
                "dbgpt.serve.auth.initial_admin_login must contain 1 to 128 characters"
            )
        try:
            password_hash = self.hash_password(self._config.initial_admin_password)
        except ValueError as exc:
            raise AuthConfigurationError(
                "dbgpt.serve.auth.initial_admin_password is invalid"
            ) from exc

        now = _utcnow()
        with self._dao.session() as session:
            if (
                session.query(UserEntity)
                .filter(
                    UserEntity.role == "system_admin",
                    UserEntity.is_active.is_(True),
                )
                .count()
                > 0
            ):
                return None
            if (
                session.query(UserEntity)
                .filter(UserEntity.login_name == login_name)
                .first()
                is not None
            ):
                raise AuthConfigurationError(
                    "dbgpt.serve.auth.initial_admin_login already exists"
                )
            user = UserEntity(
                user_id=str(uuid.uuid4()),
                login_name=login_name,
                display_name=login_name,
                password_hash=password_hash,
                role="system_admin",
                is_active=True,
                gmt_created=now,
                gmt_modified=now,
            )
            session.add(user)
            session.flush()
            session.add(
                self._audit_event(
                    action="SYSTEM.INIT_ADMIN",
                    result="success",
                    operator_user_id=user.user_id,
                    operator_role=user.role,
                    target_id=user.user_id,
                )
            )
            return UserResponse.from_entity(user)

    def _require_jwt_secret(self) -> None:
        if (
            not isinstance(self._config.jwt_secret, str)
            or len(self._config.jwt_secret.encode("utf-8")) < 32
        ):
            raise AuthConfigurationError(
                "dbgpt.serve.auth.jwt_secret must contain at least 32 bytes"
            )

    def _validate_config(self) -> None:
        if not isinstance(self._config.cookie_secure, bool):
            raise AuthConfigurationError(
                "dbgpt.serve.auth.cookie_secure must be a boolean"
            )
        positive_integer_fields = (
            "jwt_access_expire_minutes",
            "jwt_absolute_expire_minutes",
            "login_fail_lock_threshold",
            "login_fail_lock_minutes",
        )
        for field_name in positive_integer_fields:
            value = getattr(self._config, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise AuthConfigurationError(
                    f"dbgpt.serve.auth.{field_name} must be a positive integer"
                )

    @staticmethod
    def _audit_event(
        action: str,
        result: str,
        operator_user_id: Optional[str],
        operator_role: Optional[str],
        target_id: Optional[str],
        target_type: str = "USER",
        source_ip: str = "",
        user_agent: str = "",
        deny_reason: Optional[str] = None,
    ) -> AuditEventEntity:
        return AuditEventEntity(
            event_id=str(uuid.uuid4()),
            event_time=_utcnow(),
            operator_user_id=operator_user_id,
            operator_role_snapshot=operator_role,
            target_type=target_type,
            target_id=target_id,
            action=action,
            result=result,
            source_ip=(source_ip or "")[:64] or None,
            user_agent=(user_agent or "")[:512] or None,
            deny_reason=deny_reason,
        )


def get_auth_service() -> Service:
    """Resolve the initialized authorization service from the application."""
    system_app = Config().SYSTEM_APP
    if system_app is None:
        raise AuthConfigurationError("SystemApp is not initialized")
    return system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)
