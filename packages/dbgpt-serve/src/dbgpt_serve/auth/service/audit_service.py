"""Append-only audit recording and administrator queries."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from dbgpt_serve.auth.api.schemas import (
    AuditEventCreate,
    AuditEventResponse,
    AuditQueryRequest,
    Page,
)
from dbgpt_serve.auth.models.models import (
    AuditEventDao,
    AuditEventEntity,
)
from dbgpt_serve.auth.service.errors import (
    ManagementNotFoundError,
    ManagementValidationError,
)
from dbgpt_serve.auth.service.management import Operator

_SENSITIVE_MARKERS = ("password", "cookie", "token", "prompt")


class AuditService:
    """Expose append and read operations without update or delete APIs."""

    def __init__(self, dao: Optional[AuditEventDao] = None) -> None:
        self._dao = dao or AuditEventDao()

    def record(self, event: AuditEventCreate) -> AuditEventResponse:
        self._reject_sensitive_snapshot(event.before_snapshot)
        self._reject_sensitive_snapshot(event.after_snapshot)
        entity = AuditEventEntity(
            **event.model_dump(exclude={"event_id", "event_time"}),
            event_id=event.event_id or str(uuid.uuid4()),
            event_time=self._as_naive_utc(event.event_time),
        )
        return AuditEventResponse.model_validate(self._dao.append(entity))

    def query(
        self,
        filters: AuditQueryRequest,
        page: int,
        page_size: int,
        operator: Operator,
    ) -> Page[AuditEventResponse]:
        self._require_system_admin(operator)
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            query = session.query(AuditEventEntity)
            if filters.target_type:
                query = query.filter(
                    AuditEventEntity.target_type == filters.target_type
                )
            if filters.action:
                query = query.filter(AuditEventEntity.action == filters.action)
            if filters.operator_user_id:
                query = query.filter(
                    AuditEventEntity.operator_user_id == filters.operator_user_id
                )
            if filters.result:
                query = query.filter(AuditEventEntity.result == filters.result)
            if filters.date_from:
                query = query.filter(
                    AuditEventEntity.event_time >= self._as_naive_utc(filters.date_from)
                )
            if filters.date_to:
                query = query.filter(
                    AuditEventEntity.event_time <= self._as_naive_utc(filters.date_to)
                )
            total = query.count()
            entities = (
                query.order_by(
                    AuditEventEntity.event_time.desc(), AuditEventEntity.id.desc()
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [AuditEventResponse.model_validate(item) for item in entities]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def get(self, event_id: str, operator: Operator) -> AuditEventResponse:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            entity = (
                session.query(AuditEventEntity)
                .filter(AuditEventEntity.event_id == event_id)
                .first()
            )
            if entity is None:
                raise ManagementNotFoundError("Audit event does not exist")
            return AuditEventResponse.model_validate(entity)

    @staticmethod
    def _require_system_admin(operator: Operator) -> None:
        if operator.role != "system_admin" or not operator.user_id:
            raise ManagementValidationError("A system administrator is required")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ManagementValidationError(
                "page must be at least 1 and page_size must be between 1 and 100"
            )

    @staticmethod
    def _reject_sensitive_snapshot(snapshot: Optional[str]) -> None:
        normalized = (snapshot or "").lower()
        if any(marker in normalized for marker in _SENSITIVE_MARKERS):
            raise ManagementValidationError(
                "Sensitive fields are not permitted in audit snapshots"
            )

    @staticmethod
    def _as_naive_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


_audit_service = AuditService()


def get_audit_service() -> AuditService:
    return _audit_service
