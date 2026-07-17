"""Runtime capability, account-set, and concrete-resource authorization."""

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import column, select, table

from dbgpt_serve.auth.constants import ROLE_PERMISSIONS
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
    AuditEventEntity,
    UserAccountGrantEntity,
    UserDao,
    UserResourceGrantEntity,
)
from dbgpt_serve.auth.service.resources import (
    ResourceLookupError,
    ResourceRecord,
    agent_dependencies,
    get_resource_by_id_or_name,
    resolve_agent_dependency,
)
from dbgpt_serve.utils.auth import UserRequest

_USE_PERMISSIONS = {
    "DATASOURCE": "DATASOURCE_USE",
    "KNOWLEDGE_BASE": "KNOWLEDGE_BASE_USE",
    "AGENT": "AGENT_USE",
}


class AccessService:
    """Fail-closed runtime authorization using only server-side state."""

    def __init__(self, dao: Optional[UserDao] = None) -> None:
        self._dao = dao or UserDao()

    def require_capability(self, user: UserRequest, permission: str) -> None:
        if permission not in ROLE_PERMISSIONS.get(user.role or "", set()):
            self._deny(
                user,
                "CAPABILITY_MISSING",
                target_type="CAPABILITY",
                target_id=permission,
            )

    def require_account_access(
        self, user: UserRequest, account_set_id: str, permission: str
    ) -> None:
        self.require_capability(user, permission)
        if user.role == "system_admin":
            self._require_active_account_set(account_set_id, user)
            return
        if not user.user_id:
            self._deny(
                user,
                "USER_ID_MISSING",
                target_type="ACCOUNT_SET",
                target_id=account_set_id,
            )
        with self._dao.session(commit=False) as session:
            account_set = (
                session.query(AccountSetEntity.id)
                .filter(
                    AccountSetEntity.account_set_id == account_set_id,
                    AccountSetEntity.is_active.is_(True),
                )
                .first()
            )
            grant = (
                session.query(UserAccountGrantEntity.id)
                .filter(
                    UserAccountGrantEntity.user_id == user.user_id,
                    UserAccountGrantEntity.account_set_id == account_set_id,
                    UserAccountGrantEntity.is_active.is_(True),
                )
                .first()
            )
        if account_set is None:
            self._deny(
                user,
                "ACCOUNT_SET_INACTIVE",
                target_type="ACCOUNT_SET",
                target_id=account_set_id,
            )
        if grant is None:
            self._deny(
                user,
                "ACCOUNT_SET_SCOPE_MISSING",
                target_type="ACCOUNT_SET",
                target_id=account_set_id,
            )

    def require_resource_access(
        self,
        user: UserRequest,
        resource_type: str,
        resource_id_or_name: str,
        *,
        manage: bool = False,
    ) -> ResourceRecord:
        permission = (
            _USE_PERMISSIONS[resource_type]
            if not manage
            else _USE_PERMISSIONS[resource_type].replace("_USE", "_MANAGE")
        )
        self.require_capability(user, permission)
        with self._dao.session(commit=False) as session:
            try:
                resource = get_resource_by_id_or_name(
                    session, resource_type, resource_id_or_name
                )
            except ResourceLookupError:
                resource = None
            if resource is None:
                self._deny(
                    user,
                    "RESOURCE_NOT_FOUND",
                    target_type=resource_type,
                    target_id=resource_id_or_name,
                )
            if user.role == "system_admin":
                if resource.account_set_id:
                    account_set = (
                        session.query(AccountSetEntity.id)
                        .filter(
                            AccountSetEntity.account_set_id == resource.account_set_id,
                            AccountSetEntity.is_active.is_(True),
                        )
                        .first()
                    )
                    if account_set is None:
                        self._deny(
                            user,
                            "ACCOUNT_SET_INACTIVE",
                            target_type=resource_type,
                            target_id=resource.resource_id,
                        )
                return resource
            if not resource.account_set_id:
                self._deny(
                    user,
                    "RESOURCE_UNASSIGNED",
                    target_type=resource_type,
                    target_id=resource.resource_id,
                )
            account_set = (
                session.query(AccountSetEntity.id)
                .filter(
                    AccountSetEntity.account_set_id == resource.account_set_id,
                    AccountSetEntity.is_active.is_(True),
                )
                .first()
            )
            account_grant = (
                session.query(UserAccountGrantEntity.id)
                .filter(
                    UserAccountGrantEntity.user_id == user.user_id,
                    UserAccountGrantEntity.account_set_id == resource.account_set_id,
                    UserAccountGrantEntity.is_active.is_(True),
                )
                .first()
            )
            if account_set is None:
                self._deny(
                    user,
                    "ACCOUNT_SET_INACTIVE",
                    target_type=resource_type,
                    target_id=resource.resource_id,
                )
            if account_grant is None:
                self._deny(
                    user,
                    "ACCOUNT_SET_SCOPE_MISSING",
                    target_type=resource_type,
                    target_id=resource.resource_id,
                )
            if user.role == "query_user":
                resource_grant = (
                    session.query(UserResourceGrantEntity.id)
                    .filter(
                        UserResourceGrantEntity.user_id == user.user_id,
                        UserResourceGrantEntity.resource_type == resource_type,
                        UserResourceGrantEntity.resource_id == resource.resource_id,
                        UserResourceGrantEntity.account_set_id
                        == resource.account_set_id,
                        UserResourceGrantEntity.is_active.is_(True),
                    )
                    .first()
                )
                if resource_grant is None:
                    self._deny(
                        user,
                        "RESOURCE_GRANT_MISSING",
                        target_type=resource_type,
                        target_id=resource.resource_id,
                    )
                if resource_type == "AGENT":
                    self._require_agent_dependencies(session, user, resource)
            return resource

    def allowed_resource_ids(
        self, user: UserRequest, resource_type: str, *, manage: bool = False
    ) -> Optional[set[str]]:
        permission = (
            _USE_PERMISSIONS[resource_type]
            if not manage
            else _USE_PERMISSIONS[resource_type].replace("_USE", "_MANAGE")
        )
        self.require_capability(user, permission)
        if user.role == "system_admin":
            return None
        with self._dao.session(commit=False) as session:
            account_ids = {
                value
                for (value,) in session.query(UserAccountGrantEntity.account_set_id)
                .join(
                    AccountSetEntity,
                    AccountSetEntity.account_set_id
                    == UserAccountGrantEntity.account_set_id,
                )
                .filter(
                    UserAccountGrantEntity.user_id == user.user_id,
                    UserAccountGrantEntity.is_active.is_(True),
                    AccountSetEntity.is_active.is_(True),
                )
                .all()
            }
            if user.role != "query_user":
                from dbgpt_serve.auth.service.resources import list_resources

                return {
                    item.resource_id
                    for item in list_resources(
                        session, resource_type, account_set_ids=account_ids
                    )
                }
            return {
                resource_id
                for (resource_id,) in session.query(UserResourceGrantEntity.resource_id)
                .filter(
                    UserResourceGrantEntity.user_id == user.user_id,
                    UserResourceGrantEntity.resource_type == resource_type,
                    UserResourceGrantEntity.account_set_id.in_(account_ids),
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .all()
            }

    def require_document_access(
        self, user: UserRequest, document_id: str, *, manage: bool = False
    ) -> ResourceRecord:
        try:
            numeric_document_id = int(document_id)
        except (TypeError, ValueError):
            self._deny(
                user,
                "DOCUMENT_ID_INVALID",
                target_type="KNOWLEDGE_DOCUMENT",
                target_id=str(document_id),
            )
        document_table = table("knowledge_document", column("id"), column("space"))
        with self._dao.session(commit=False) as session:
            space_name = session.execute(
                select(document_table.c.space).where(
                    document_table.c.id == numeric_document_id
                )
            ).scalar_one_or_none()
        if not space_name:
            self._deny(
                user,
                "DOCUMENT_NOT_FOUND",
                target_type="KNOWLEDGE_DOCUMENT",
                target_id=document_id,
            )
        return self.require_resource_access(
            user, "KNOWLEDGE_BASE", str(space_name), manage=manage
        )

    def require_chat_access(
        self,
        user: UserRequest,
        chat_mode: Optional[str],
        chat_param: Optional[str],
        app_code: Optional[str] = None,
    ) -> None:
        self.require_capability(user, "CHAT_USE")
        normalized_mode = (chat_mode or "").lower()
        if "agent" in normalized_mode or "app" in normalized_mode:
            target = app_code or chat_param
            if target:
                self.require_resource_access(user, "AGENT", str(target))
        elif "knowledge" in normalized_mode:
            if chat_param:
                self.require_resource_access(user, "KNOWLEDGE_BASE", str(chat_param))
        elif any(marker in normalized_mode for marker in ("data", "db", "dashboard")):
            if chat_param:
                self.require_resource_access(user, "DATASOURCE", str(chat_param))

    def require_agent_definition_access(
        self, user: UserRequest, account_set_id: str, details
    ) -> None:
        self.require_account_access(user, account_set_id, "AGENT_MANAGE")
        dependencies: dict[tuple[str, str], ResourceRecord] = {}
        with self._dao.session(commit=False) as session:
            for detail in details or []:
                for resource in detail.resources or []:
                    try:
                        dependency = resolve_agent_dependency(
                            session, "pending-agent", resource.to_dict()
                        )
                    except ResourceLookupError:
                        self._deny(
                            user,
                            "AGENT_DEPENDENCY_INVALID",
                            target_type="AGENT",
                            target_id=None,
                        )
                    if dependency is not None:
                        dependencies[
                            (dependency.resource_type, dependency.resource_id)
                        ] = dependency
        for dependency in dependencies.values():
            if dependency.account_set_id != account_set_id:
                self._deny(
                    user,
                    "AGENT_DEPENDENCY_SCOPE_MISMATCH",
                    target_type="AGENT",
                    target_id=None,
                )
            self.require_resource_access(
                user,
                dependency.resource_type,
                dependency.resource_id,
                manage=True,
            )

    def allowed_resource_names(
        self, user: UserRequest, resource_type: str, *, manage: bool = False
    ) -> Optional[set[str]]:
        allowed_ids = self.allowed_resource_ids(user, resource_type, manage=manage)
        if allowed_ids is None:
            return None
        from dbgpt_serve.auth.service.resources import list_resources

        with self._dao.session(commit=False) as session:
            return {
                item.name
                for item in list_resources(session, resource_type)
                if item.resource_id in allowed_ids
            }

    def _require_agent_dependencies(
        self, session, user: UserRequest, agent: ResourceRecord
    ) -> None:
        try:
            dependencies = agent_dependencies(session, agent.resource_id)
        except ResourceLookupError:
            self._deny(
                user,
                "AGENT_DEPENDENCY_INVALID",
                target_type="AGENT",
                target_id=agent.resource_id,
            )
        for dependency in dependencies:
            if dependency.account_set_id != agent.account_set_id:
                self._deny(
                    user,
                    "AGENT_DEPENDENCY_SCOPE_MISMATCH",
                    target_type="AGENT",
                    target_id=agent.resource_id,
                )
            grant = (
                session.query(UserResourceGrantEntity.id)
                .filter(
                    UserResourceGrantEntity.user_id == user.user_id,
                    UserResourceGrantEntity.resource_type == dependency.resource_type,
                    UserResourceGrantEntity.resource_id == dependency.resource_id,
                    UserResourceGrantEntity.account_set_id == dependency.account_set_id,
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .first()
            )
            if grant is None:
                self._deny(
                    user,
                    "AGENT_DEPENDENCY_GRANT_MISSING",
                    target_type="AGENT",
                    target_id=agent.resource_id,
                )

    def _require_active_account_set(
        self, account_set_id: str, user: UserRequest
    ) -> None:
        with self._dao.session(commit=False) as session:
            exists = (
                session.query(AccountSetEntity.id)
                .filter(
                    AccountSetEntity.account_set_id == account_set_id,
                    AccountSetEntity.is_active.is_(True),
                )
                .first()
            )
        if exists is None:
            self._deny(
                user,
                "ACCOUNT_SET_INACTIVE",
                target_type="ACCOUNT_SET",
                target_id=account_set_id,
            )

    def _deny(
        self,
        user: UserRequest,
        reason: str,
        *,
        target_type: str,
        target_id: Optional[str],
    ) -> None:
        with self._dao.session() as session:
            event = AuditEventEntity(
                event_id=str(uuid.uuid4()),
                operator_user_id=user.user_id,
                operator_role_snapshot=user.role,
                target_type=target_type,
                target_id=target_id,
                action="AUTHZ.CHECK",
                result="denied",
                source_ip=user.source_ip,
                user_agent=user.user_agent,
                request_id=user.request_id,
                deny_reason=reason,
            )
            session.add(event)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": reason, "message": "Access denied"},
        )


_access_service = AccessService()


def get_access_service() -> AccessService:
    return _access_service
