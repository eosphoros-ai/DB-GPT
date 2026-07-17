"""Database entities and DAOs for the authorization center."""

from datetime import datetime
from typing import Any, Dict, Optional, Union

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from dbgpt.storage.metadata import BaseDao, Model
from dbgpt.util.pagination_utils import PaginationResult


class UserEntity(Model):
    """DB-GPT user account."""

    __tablename__ = "dbgpt_auth_user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False)
    login_name = Column(String(128), nullable=False)
    display_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    activation_token = Column(String(255), nullable=True)
    activation_token_exp = Column(DateTime, nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_exp = Column(DateTime, nullable=True)
    login_fail_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_by = Column(String(128), nullable=True)
    disabled_by = Column(String(128), nullable=True)
    disabled_at = Column(DateTime, nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uk_dbgpt_auth_user_user_id"),
        UniqueConstraint("login_name", name="uk_dbgpt_auth_user_login_name"),
        Index("ix_dbgpt_auth_user_user_id", "user_id"),
        Index("ix_dbgpt_auth_user_login_name", "login_name"),
    )


class AccountSetEntity(Model):
    """ERP or MES account set managed by DB-GPT."""

    __tablename__ = "dbgpt_auth_account_set"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_set_id = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(128), nullable=False)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint(
            "account_set_id", name="uk_dbgpt_auth_account_set_business_id"
        ),
        UniqueConstraint("name", name="uk_dbgpt_auth_account_set_name"),
        Index("ix_dbgpt_auth_account_set_id", "account_set_id"),
    )


class UserAccountGrantEntity(Model):
    """Account-set scope granted to a user."""

    __tablename__ = "dbgpt_auth_user_account_grant"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grant_id = Column(String(128), nullable=False)
    user_id = Column(String(128), nullable=False)
    account_set_id = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    granted_by = Column(String(128), nullable=False)
    revoked_by = Column(String(128), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoke_reason = Column(Text, nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint("grant_id", name="uk_dbgpt_auth_user_account_grant_id"),
        UniqueConstraint(
            "user_id",
            "account_set_id",
            name="uk_dbgpt_auth_user_account_grant_scope",
        ),
        Index("ix_dbgpt_auth_user_account_grant_id", "grant_id"),
        Index("ix_dbgpt_auth_user_account_grant_user_id", "user_id"),
        Index("ix_dbgpt_auth_user_account_grant_account_set_id", "account_set_id"),
    )


class UserResourceGrantEntity(Model):
    """Specific resource granted to a query user."""

    __tablename__ = "dbgpt_auth_user_resource_grant"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grant_id = Column(String(128), nullable=False)
    user_id = Column(String(128), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=False)
    account_set_id = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    granted_by = Column(String(128), nullable=False)
    revoked_by = Column(String(128), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoke_reason = Column(Text, nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint("grant_id", name="uk_dbgpt_auth_user_resource_grant_id"),
        UniqueConstraint(
            "user_id",
            "resource_type",
            "resource_id",
            name="uk_dbgpt_auth_user_resource_grant_resource",
        ),
        Index("ix_dbgpt_auth_user_resource_grant_id", "grant_id"),
        Index("ix_dbgpt_auth_user_resource_grant_user_id", "user_id"),
        Index("ix_dbgpt_auth_user_resource_grant_resource_id", "resource_id"),
    )


class ImportBatchEntity(Model):
    """Audit summary for a one-time external user import."""

    __tablename__ = "dbgpt_auth_import_batch"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(128), nullable=False, unique=True)
    operator_user_id = Column(String(128), nullable=False)
    source_name = Column(String(255), nullable=False)
    selected_count = Column(Integer, nullable=False)
    created_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    selected_summary = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)


class TokenUsageEntity(Model):
    """One physical model call and its metering result."""

    __tablename__ = "dbgpt_auth_token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(128), nullable=False)
    request_id = Column(String(128), nullable=False)
    session_id = Column(String(128), nullable=True)
    user_id = Column(String(128), nullable=False)
    role_snapshot = Column(String(64), nullable=False)
    account_set_id = Column(String(128), nullable=True)
    account_set_snapshot = Column(String(255), nullable=True)
    entry_resource_type = Column(String(64), nullable=True)
    entry_resource_id = Column(String(128), nullable=True)
    agent_id = Column(String(128), nullable=True)
    model = Column(String(255), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    metering_source = Column(String(64), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)
    error_type = Column(String(64), nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("call_id", name="uk_dbgpt_auth_token_usage_call_id"),
        Index("ix_dbgpt_auth_token_usage_call_id", "call_id"),
        Index("ix_dbgpt_auth_token_usage_request_id", "request_id"),
        Index("ix_dbgpt_auth_token_usage_session_id", "session_id"),
        Index("ix_dbgpt_auth_token_usage_user_id", "user_id"),
        Index("ix_dbgpt_auth_token_usage_account_set_id", "account_set_id"),
        Index("ix_dbgpt_auth_token_usage_gmt_created", "gmt_created"),
    )


class TokenDailyEntity(Model):
    """Daily token aggregation in the Asia/Shanghai reporting timezone."""

    __tablename__ = "dbgpt_auth_token_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(String(10), nullable=False)
    user_id = Column(String(128), nullable=False)
    role_snapshot = Column(String(64), nullable=False)
    account_set_id = Column(String(128), nullable=False, default="")
    model = Column(String(255), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    call_count = Column(Integer, nullable=False, default=0)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint(
            "stat_date",
            "user_id",
            "role_snapshot",
            "account_set_id",
            "model",
            name="uk_dbgpt_auth_token_daily_dimensions",
        ),
        Index("ix_dbgpt_auth_token_daily_stat_date", "stat_date"),
        Index("ix_dbgpt_auth_token_daily_user_id", "user_id"),
        Index("ix_dbgpt_auth_token_daily_account_set_id", "account_set_id"),
    )


class AuditEventEntity(Model):
    """Append-only security and administrative audit event."""

    __tablename__ = "dbgpt_auth_audit_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), nullable=False)
    event_time = Column(DateTime, nullable=False, default=datetime.now)
    operator_user_id = Column(String(128), nullable=True)
    operator_role_snapshot = Column(String(64), nullable=True)
    target_account_set_id = Column(String(128), nullable=True)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(128), nullable=True)
    action = Column(String(64), nullable=False)
    result = Column(String(32), nullable=False)
    source_ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    request_id = Column(String(128), nullable=True)
    before_snapshot = Column(Text, nullable=True)
    after_snapshot = Column(Text, nullable=True)
    deny_reason = Column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("event_id", name="uk_dbgpt_auth_audit_event_id"),
        Index("ix_dbgpt_auth_audit_event_event_id", "event_id"),
        Index("ix_dbgpt_auth_audit_event_event_time", "event_time"),
        Index("ix_dbgpt_auth_audit_event_operator_user_id", "operator_user_id"),
        Index(
            "ix_dbgpt_auth_audit_event_target_account_set_id",
            "target_account_set_id",
        ),
        Index("ix_dbgpt_auth_audit_event_target_type", "target_type"),
        Index("ix_dbgpt_auth_audit_event_target_id", "target_id"),
        Index("ix_dbgpt_auth_audit_event_request_id", "request_id"),
    )


class SessionEntity(Model):
    """Server-side state for a revocable authenticated session."""

    __tablename__ = "dbgpt_auth_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False)
    user_id = Column(String(128), nullable=False)
    issued_at = Column(DateTime, nullable=False, default=datetime.now)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.now)
    idle_expires_at = Column(DateTime, nullable=False)
    absolute_expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(String(128), nullable=True)
    revoke_reason = Column(String(512), nullable=True)
    source_ip = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    __table_args__ = (
        UniqueConstraint("session_id", name="uk_dbgpt_auth_session_id"),
        Index("ix_dbgpt_auth_session_id", "session_id"),
        Index("ix_dbgpt_auth_session_user_id", "user_id"),
        Index("ix_dbgpt_auth_session_idle_expires_at", "idle_expires_at"),
        Index("ix_dbgpt_auth_session_absolute_expires_at", "absolute_expires_at"),
    )


class _EntityDao(BaseDao):
    """Common private helpers for entity-specific DAOs."""

    entity_type: Any

    def _get_one(self, **filters: Any) -> Any:
        with self.session(commit=False) as session:
            return session.query(self.entity_type).filter_by(**filters).first()


class UserDao(_EntityDao):
    """Persistence operations for DB-GPT users."""

    entity_type = UserEntity

    def get_by_user_id(self, user_id: str) -> Optional[UserEntity]:
        return self._get_one(user_id=user_id)

    def get_by_login_name(self, login_name: str) -> Optional[UserEntity]:
        return self._get_one(login_name=login_name)

    def count_active_admins(self) -> int:
        with self.session(commit=False) as session:
            return (
                session.query(UserEntity)
                .filter(
                    UserEntity.role == "system_admin",
                    UserEntity.is_active.is_(True),
                )
                .count()
            )


class AccountSetDao(_EntityDao):
    """Persistence operations for account sets."""

    entity_type = AccountSetEntity

    def get_by_account_set_id(self, account_set_id: str) -> Optional[AccountSetEntity]:
        return self._get_one(account_set_id=account_set_id)


class UserAccountGrantDao(_EntityDao):
    """Persistence operations for user account-set grants."""

    entity_type = UserAccountGrantEntity

    def get_by_grant_id(self, grant_id: str) -> Optional[UserAccountGrantEntity]:
        return self._get_one(grant_id=grant_id)

    def has_active_grant(self, user_id: str, account_set_id: str) -> bool:
        with self.session(commit=False) as session:
            return (
                session.query(UserAccountGrantEntity.id)
                .filter(
                    UserAccountGrantEntity.user_id == user_id,
                    UserAccountGrantEntity.account_set_id == account_set_id,
                    UserAccountGrantEntity.is_active.is_(True),
                )
                .first()
                is not None
            )


class UserResourceGrantDao(_EntityDao):
    """Persistence operations for query-user resource grants."""

    entity_type = UserResourceGrantEntity

    def get_by_grant_id(self, grant_id: str) -> Optional[UserResourceGrantEntity]:
        return self._get_one(grant_id=grant_id)

    def has_active_grant(
        self, user_id: str, resource_type: str, resource_id: str
    ) -> bool:
        with self.session(commit=False) as session:
            return (
                session.query(UserResourceGrantEntity.id)
                .filter(
                    UserResourceGrantEntity.user_id == user_id,
                    UserResourceGrantEntity.resource_type == resource_type,
                    UserResourceGrantEntity.resource_id == resource_id,
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .first()
                is not None
            )


class ImportBatchDao(_EntityDao):
    """Persistence operations for account import batches."""

    entity_type = ImportBatchEntity

    def get_by_batch_id(self, batch_id: str) -> Optional[ImportBatchEntity]:
        return self._get_one(batch_id=batch_id)


class TokenUsageDao(_EntityDao):
    """Persistence operations for model call usage details."""

    entity_type = TokenUsageEntity

    def get_by_call_id(self, call_id: str) -> Optional[TokenUsageEntity]:
        return self._get_one(call_id=call_id)


class TokenDailyDao(_EntityDao):
    """Persistence operations for daily token aggregations."""

    entity_type = TokenDailyEntity

    def get_by_dimensions(
        self,
        stat_date: str,
        user_id: str,
        role_snapshot: str,
        account_set_id: Optional[str],
        model: str,
    ) -> Optional[TokenDailyEntity]:
        with self.session(commit=False) as session:
            return (
                session.query(TokenDailyEntity)
                .filter(
                    TokenDailyEntity.stat_date == stat_date,
                    TokenDailyEntity.user_id == user_id,
                    TokenDailyEntity.role_snapshot == role_snapshot,
                    TokenDailyEntity.account_set_id == (account_set_id or ""),
                    TokenDailyEntity.model == model,
                )
                .first()
            )


class SessionDao(_EntityDao):
    """Persistence operations for authenticated sessions."""

    entity_type = SessionEntity

    def get_by_session_id(self, session_id: str) -> Optional[SessionEntity]:
        return self._get_one(session_id=session_id)

    def get_active_session(
        self, session_id: str, user_id: str, now: Optional[datetime] = None
    ) -> Optional[SessionEntity]:
        current_time = now or datetime.now()
        with self.session(commit=False) as session:
            return (
                session.query(SessionEntity)
                .filter(
                    SessionEntity.session_id == session_id,
                    SessionEntity.user_id == user_id,
                    SessionEntity.revoked_at.is_(None),
                    SessionEntity.idle_expires_at > current_time,
                    SessionEntity.absolute_expires_at > current_time,
                )
                .first()
            )


class AuditEventDao(BaseDao):
    """Append-only persistence operations for audit events."""

    _FILTER_FIELDS = {
        "operator_user_id",
        "target_account_set_id",
        "target_type",
        "target_id",
        "action",
        "result",
        "request_id",
    }

    def append(
        self, event: Union[AuditEventEntity, Dict[str, Any]]
    ) -> AuditEventEntity:
        entity = (
            event if isinstance(event, AuditEventEntity) else AuditEventEntity(**event)
        )
        with self.session() as session:
            session.add(entity)
            session.flush()
            session.expunge(entity)
        return entity

    def query(
        self, filters: Dict[str, Any], page: int, page_size: int
    ) -> PaginationResult[AuditEventEntity]:
        unknown_fields = set(filters) - self._FILTER_FIELDS
        if unknown_fields:
            raise ValueError(f"Unsupported audit filters: {sorted(unknown_fields)}")
        with self.session(commit=False) as session:
            query = session.query(AuditEventEntity)
            for field, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(AuditEventEntity, field) == value)
            total_count = query.count()
            items = (
                query.order_by(AuditEventEntity.event_time.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return PaginationResult(
                items=items,
                total_count=total_count,
                total_pages=(total_count + page_size - 1) // page_size,
                page=page,
                page_size=page_size,
            )

    def create(self, request: Any) -> Any:
        raise TypeError("Audit events must be written with append()")

    def update(self, query_request: Any, update_request: Any) -> Any:
        raise TypeError("Audit events are append-only")

    def delete(self, query_request: Any) -> None:
        raise TypeError("Audit events are append-only")
