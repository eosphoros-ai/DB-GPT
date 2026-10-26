"""Dashboard-scoped authorization and redacted audit logging."""

import importlib
import json
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Set

from .models import (
    DashboardAccessDao,
    DashboardAccessDeniedError,
    DashboardAuditDao,
    DashboardAuditEntity,
    DashboardDao,
    DashboardEntity,
    DashboardNotFoundError,
)
from .schemas import (
    DashboardAction,
    DashboardAuditRecord,
    DashboardMemberRecord,
    DashboardPermissionRecord,
    DashboardRole,
)

_ROLE_ACTIONS: Dict[DashboardRole, Set[DashboardAction]] = {
    DashboardRole.VIEWER: {DashboardAction.VIEW},
    DashboardRole.EDITOR: {
        DashboardAction.VIEW,
        DashboardAction.EDIT,
        DashboardAction.QUERY,
    },
    DashboardRole.OWNER: set(DashboardAction),
}

_SENSITIVE_DETAIL_PARTS = ("token", "secret", "password", "credential", "sql", "param")


class DashboardDataSourcePolicy(Protocol):
    """Platform-owned authorization decision for one actor and data source."""

    def can_query(self, actor_id: str, data_source_id: str) -> bool: ...


class CallableDashboardDataSourcePolicy:
    """Backward-compatible adapter for existing callable integrations."""

    def __init__(self, authorizer: Callable[[str, str], bool]) -> None:
        self._authorizer = authorizer

    def can_query(self, actor_id: str, data_source_id: str) -> bool:
        return bool(self._authorizer(actor_id, data_source_id))


def load_dashboard_data_source_policy(path: str) -> DashboardDataSourcePolicy:
    """Load a deployment-owned policy without coupling Dashboard to one IAM."""

    module_name, separator, attribute = path.rpartition(".")
    if not separator:
        raise RuntimeError(
            "DBGPT_DASHBOARD_DATA_SOURCE_POLICY must be a dotted import path."
        )
    policy_type = getattr(importlib.import_module(module_name), attribute)
    policy = policy_type() if isinstance(policy_type, type) else policy_type
    if not callable(getattr(policy, "can_query", None)):
        raise RuntimeError(
            "Dashboard data-source policy must define can_query(actor_id, source_id)."
        )
    return policy


def _redact_details(value: Any, *, key: str = "") -> Any:
    """Keep audit metadata useful without persisting secrets, SQL, or data rows."""

    lowered = key.lower()
    if any(part in lowered for part in _SENSITIVE_DETAIL_PARTS):
        return "[redacted]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(item_key): _redact_details(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_redact_details(item, key=key) for item in value]
    return str(value)


class DashboardAuthorizationService:
    """Deny-by-default role checks for one dashboard.

    ``data_source_authorizer`` is an integration hook for deployments that have a
    central data-source policy service.  It receives ``(actor_id, source_id)`` and
    must return ``True``.  Dashboard role checks are always applied first.
    """

    def __init__(
        self,
        dashboard_dao: Optional[DashboardDao] = None,
        access_dao: Optional[DashboardAccessDao] = None,
        audit_dao: Optional[DashboardAuditDao] = None,
        data_source_authorizer: Optional[Callable[[str, str], bool]] = None,
        data_source_policy: Optional[DashboardDataSourcePolicy] = None,
        require_data_source_authorizer: Optional[bool] = None,
    ) -> None:
        self.dashboard_dao = dashboard_dao or DashboardDao()
        self.access_dao = access_dao or DashboardAccessDao()
        self.audit_dao = audit_dao or DashboardAuditDao()
        self._data_source_authorizer = data_source_authorizer
        if data_source_authorizer is not None and data_source_policy is not None:
            raise ValueError(
                "Configure either data_source_policy or data_source_authorizer, "
                "not both."
            )
        self._data_source_policy = data_source_policy
        policy_path = os.getenv("DBGPT_DASHBOARD_DATA_SOURCE_POLICY", "").strip()
        if self._data_source_policy is None and policy_path:
            self._data_source_policy = load_dashboard_data_source_policy(policy_path)
        if self._data_source_policy is None and data_source_authorizer is not None:
            self._data_source_policy = CallableDashboardDataSourcePolicy(
                data_source_authorizer
            )
        if require_data_source_authorizer is None:
            require_data_source_authorizer = os.getenv(
                "DBGPT_DASHBOARD_REQUIRE_DATA_SOURCE_AUTHORIZATION", ""
            ).strip().lower() in {"1", "true", "yes", "on"} or os.getenv(
                "DBGPT_DASHBOARD_PRODUCTION_MODE", ""
            ).strip().lower() in {"1", "true", "yes", "on"}
        self._require_data_source_authorizer = require_data_source_authorizer

    @staticmethod
    def actions_for_role(role: DashboardRole) -> List[DashboardAction]:
        return sorted(_ROLE_ACTIONS[role], key=lambda item: item.value)

    def ensure_owner(self, dashboard_id: str, owner_id: str) -> None:
        self.access_dao.ensure_owner(dashboard_id, owner_id)

    def resolve_role(
        self, dashboard: DashboardEntity, actor_id: str
    ) -> Optional[DashboardRole]:
        if actor_id == dashboard.owner_id:
            return DashboardRole.OWNER
        member = self.access_dao.get_member(dashboard.id, actor_id)
        if member is None:
            return None
        try:
            return DashboardRole(member.role)
        except ValueError:
            return None

    def require_data_sources(
        self, actor_id: str, data_source_ids: Iterable[str]
    ) -> None:
        """Authorize sources before schema validation can resolve a connector.

        Creation does not yet have a dashboard row on which to perform an RBAC
        check. Schema edits can also introduce a source before a query endpoint is
        called. Keeping this check separate lets both paths fail closed before any
        database metadata or rows are accessed.
        """

        source_ids = sorted({source_id for source_id in data_source_ids if source_id})
        if not source_ids:
            return
        policy = self._data_source_policy
        if policy is None and self._data_source_authorizer is not None:
            policy = CallableDashboardDataSourcePolicy(self._data_source_authorizer)
        if policy is None and self._require_data_source_authorizer:
            raise DashboardAccessDeniedError(
                "Data-source authorization is required but no platform policy "
                "adapter is configured."
            )
        if policy is None:
            return
        for source_id in source_ids:
            if not policy.can_query(actor_id, source_id):
                raise DashboardAccessDeniedError(
                    f"Actor '{actor_id}' cannot query data source '{source_id}'."
                )

    def require(
        self,
        dashboard_id: str,
        actor_id: str,
        action: DashboardAction,
        *,
        data_source_ids: Optional[Iterable[str]] = None,
    ) -> DashboardEntity:
        dashboard = self.dashboard_dao.get_dashboard_by_id(dashboard_id)
        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)
        role = self.resolve_role(dashboard, actor_id)
        if role is None or action not in _ROLE_ACTIONS[role]:
            raise DashboardAccessDeniedError(
                f"Actor '{actor_id}' is not allowed to {action.value} dashboard "
                f"'{dashboard_id}'."
            )
        if action == DashboardAction.QUERY:
            self.require_data_sources(actor_id, data_source_ids or [])
        return dashboard

    def permissions(
        self, dashboard_id: str, actor_id: str
    ) -> DashboardPermissionRecord:
        dashboard = self.require(dashboard_id, actor_id, DashboardAction.VIEW)
        role = self.resolve_role(dashboard, actor_id)
        if role is None:  # pragma: no cover - guarded by require
            raise DashboardAccessDeniedError(actor_id)
        return DashboardPermissionRecord(
            dashboard_id=dashboard_id,
            actor_id=actor_id,
            role=role,
            actions=self.actions_for_role(role),
        )

    def list_accessible(
        self,
        actor_id: str,
        *,
        conversation_id: Optional[str] = None,
        origin: Optional[str] = None,
        exclude_origin: Optional[str] = None,
        asset_state: Optional[str] = None,
        status: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[DashboardEntity]:
        page_size = 100
        rows, total = self.access_dao.list_accessible_dashboards(
            actor_id,
            conversation_id=conversation_id,
            origin=origin,
            exclude_origin=exclude_origin,
            asset_state=asset_state,
            status=status,
            include_archived=include_archived,
            limit=page_size,
            offset=0,
        )
        while len(rows) < total:
            page, _ = self.access_dao.list_accessible_dashboards(
                actor_id,
                conversation_id=conversation_id,
                origin=origin,
                exclude_origin=exclude_origin,
                asset_state=asset_state,
                status=status,
                include_archived=include_archived,
                limit=page_size,
                offset=len(rows),
            )
            if not page:
                break
            rows.extend(page)
        return rows

    def list_accessible_page(
        self,
        actor_id: str,
        *,
        folder_id: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None,
        conversation_id: Optional[str] = None,
        origin: Optional[str] = None,
        exclude_origin: Optional[str] = None,
        asset_state: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 24,
        offset: int = 0,
    ):
        return self.access_dao.list_accessible_dashboards(
            actor_id,
            search=search,
            folder_id=folder_id,
            status=status,
            conversation_id=conversation_id,
            origin=origin,
            exclude_origin=exclude_origin,
            asset_state=asset_state,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    def list_members(
        self, dashboard_id: str, actor_id: str
    ) -> List[DashboardMemberRecord]:
        self.require(dashboard_id, actor_id, DashboardAction.MANAGE_ACCESS)
        return [
            self._member_record(item)
            for item in self.access_dao.list_members(dashboard_id)
        ]

    def upsert_member(
        self,
        dashboard_id: str,
        actor_id: str,
        principal_id: str,
        role: DashboardRole,
        *,
        request_id: Optional[str] = None,
    ) -> DashboardMemberRecord:
        dashboard = self.require(dashboard_id, actor_id, DashboardAction.MANAGE_ACCESS)
        if role == DashboardRole.OWNER:
            raise ValueError(
                "The owner role cannot be assigned through member updates; use an "
                "explicit ownership-transfer workflow."
            )
        if principal_id == dashboard.owner_id:
            raise ValueError("The dashboard owner cannot be downgraded.")
        member = self.access_dao.upsert_member(
            dashboard_id, principal_id, role.value, actor_id
        )
        self.audit(
            dashboard_id,
            actor_id,
            "member.upserted",
            target_type="member",
            target_id=principal_id,
            details={"role": role.value},
            request_id=request_id,
        )
        return self._member_record(member)

    def remove_member(
        self,
        dashboard_id: str,
        actor_id: str,
        principal_id: str,
        *,
        request_id: Optional[str] = None,
    ) -> bool:
        dashboard = self.require(dashboard_id, actor_id, DashboardAction.MANAGE_ACCESS)
        if principal_id == dashboard.owner_id:
            raise ValueError("The dashboard owner cannot be removed.")
        removed = self.access_dao.delete_member(dashboard_id, principal_id)
        if removed:
            self.audit(
                dashboard_id,
                actor_id,
                "member.removed",
                target_type="member",
                target_id=principal_id,
                request_id=request_id,
            )
        return removed

    def audit(
        self,
        dashboard_id: str,
        actor_id: str,
        action: str,
        *,
        target_type: str = "dashboard",
        target_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> DashboardAuditRecord:
        safe_details = _redact_details(details or {})
        entity = self.audit_dao.append(
            DashboardAuditEntity(
                dashboard_id=dashboard_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details_json=json.dumps(
                    safe_details, ensure_ascii=False, separators=(",", ":")
                ),
                request_id=request_id,
            )
        )
        return self._audit_record(entity)

    def list_audit(
        self,
        dashboard_id: str,
        actor_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DashboardAuditRecord]:
        self.require(dashboard_id, actor_id, DashboardAction.MANAGE_ACCESS)
        return [
            self._audit_record(item)
            for item in self.audit_dao.list_for_dashboard(
                dashboard_id, limit=limit, offset=offset
            )
        ]

    @staticmethod
    def _member_record(entity) -> DashboardMemberRecord:
        return DashboardMemberRecord(
            dashboard_id=entity.dashboard_id,
            principal_id=entity.principal_id,
            role=entity.role,
            created_by=entity.created_by,
            created_at=entity.gmt_created,
            updated_at=entity.gmt_modified,
        )

    @staticmethod
    def _audit_record(entity) -> DashboardAuditRecord:
        try:
            details = json.loads(entity.details_json or "{}")
        except json.JSONDecodeError:
            details = {"invalid_details": True}
        return DashboardAuditRecord(
            id=entity.id,
            dashboard_id=entity.dashboard_id,
            actor_id=entity.actor_id,
            action=entity.action,
            target_type=entity.target_type,
            target_id=entity.target_id,
            details=details,
            request_id=entity.request_id,
            created_at=entity.gmt_created,
        )
