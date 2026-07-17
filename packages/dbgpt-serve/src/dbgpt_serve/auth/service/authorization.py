"""Transactional account-set and protected-resource authorization management."""

import hashlib
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError

from dbgpt_serve.auth.api.schemas import (
    AssignResourceAccountRequest,
    ConfirmRevokeRequest,
    Page,
    ResourceImpactResponse,
    ResourceResponse,
    RevokeImpactResponse,
    RevokeRequest,
    UserAccountGrantResponse,
    UserResourceGrantResponse,
)
from dbgpt_serve.auth.constants import ROLE_PERMISSIONS
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
    UserAccountGrantEntity,
    UserEntity,
    UserResourceGrantEntity,
)
from dbgpt_serve.auth.service.errors import (
    ImpactConfirmationRequiredError,
    ManagementConflictError,
    ManagementNotFoundError,
    ManagementValidationError,
)
from dbgpt_serve.auth.service.management import Operator, _json_summary, _utcnow
from dbgpt_serve.auth.service.resources import (
    RESOURCE_DEFINITIONS,
    ResourceLookupError,
    ResourceRecord,
    agent_dependencies,
    count_resources,
    dependent_agent_ids,
    get_resource,
    list_resources,
)
from dbgpt_serve.auth.service.resources import (
    assign_resource_account as persist_resource_account,
)

_RESOURCE_MANAGE_PERMISSIONS = {
    "DATASOURCE": "DATASOURCE_MANAGE",
    "KNOWLEDGE_BASE": "KNOWLEDGE_BASE_MANAGE",
    "AGENT": "AGENT_MANAGE",
}


class AuthorizationMixin:
    """Authorization administration methods mixed into the auth service."""

    def grant_user_account(
        self, user_id: str, account_set_id: str, operator: Operator
    ) -> UserAccountGrantResponse:
        operator_id = self._require_system_admin(operator)
        now = _utcnow()
        try:
            with self._dao.session() as session:
                user = self._locked_user(session, user_id)
                if user.role == "system_admin":
                    raise ManagementValidationError(
                        "System administrators do not require account-set grants"
                    )
                account_set = self._active_account_set(session, account_set_id)
                grant = (
                    session.query(UserAccountGrantEntity)
                    .filter(
                        UserAccountGrantEntity.user_id == user.user_id,
                        UserAccountGrantEntity.account_set_id
                        == account_set.account_set_id,
                    )
                    .with_for_update()
                    .first()
                )
                before = self._account_grant_snapshot(grant) if grant else None
                if grant is not None and grant.is_active:
                    raise ManagementConflictError(
                        "The user already has this account-set grant"
                    )
                if grant is None:
                    grant = UserAccountGrantEntity(
                        grant_id=str(uuid.uuid4()),
                        user_id=user.user_id,
                        account_set_id=account_set.account_set_id,
                        is_active=True,
                        granted_by=operator_id,
                        gmt_created=now,
                        gmt_modified=now,
                    )
                    session.add(grant)
                else:
                    grant.is_active = True
                    grant.granted_by = operator_id
                    grant.revoked_by = None
                    grant.revoked_at = None
                    grant.revoke_reason = None
                    grant.gmt_modified = now
                session.flush()
                self._append_audit(
                    session,
                    action="USER_ACCOUNT_GRANT.GRANT",
                    operator=operator,
                    target_type="USER_ACCOUNT_GRANT",
                    target_id=grant.grant_id,
                    target_account_set_id=grant.account_set_id,
                    before=before,
                    after=self._account_grant_snapshot(grant),
                )
                response = UserAccountGrantResponse.model_validate(grant)
        except IntegrityError as exc:
            raise ManagementConflictError(
                "The user already has this account-set grant"
            ) from exc
        return response

    def list_user_account_grants(
        self,
        user_id: str,
        page: int,
        page_size: int,
        operator: Operator,
        is_active: Optional[bool] = None,
    ) -> Page[UserAccountGrantResponse]:
        self._require_system_admin(operator)
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            self._existing_user(session, user_id)
            query = session.query(UserAccountGrantEntity).filter(
                UserAccountGrantEntity.user_id == user_id
            )
            if is_active is not None:
                query = query.filter(UserAccountGrantEntity.is_active.is_(is_active))
            total = query.count()
            entities = (
                query.order_by(
                    UserAccountGrantEntity.gmt_created.desc(),
                    UserAccountGrantEntity.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [
                UserAccountGrantResponse.model_validate(entity) for entity in entities
            ]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def get_user_account_revoke_impact(
        self, user_id: str, grant_id: str, operator: Operator
    ) -> RevokeImpactResponse:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            grant = self._account_grant(session, user_id, grant_id)
            return self._account_grant_impact(session, grant)

    def revoke_user_account(
        self,
        user_id: str,
        grant_id: str,
        request: ConfirmRevokeRequest,
        operator: Operator,
    ) -> RevokeImpactResponse:
        operator_id = self._require_system_admin(operator)
        now = _utcnow()
        with self._dao.session() as session:
            grant = self._account_grant(session, user_id, grant_id, for_update=True)
            if not grant.is_active:
                raise ManagementConflictError("The account-set grant is not active")
            impact = self._account_grant_impact(session, grant)
            if (
                not request.confirm_impact
                or request.impact_token != impact.impact_token
            ):
                raise ImpactConfirmationRequiredError(
                    "Account-set grant revocation requires current impact confirmation"
                )
            before = self._account_grant_snapshot(grant)
            grants = (
                session.query(UserResourceGrantEntity)
                .filter(
                    UserResourceGrantEntity.user_id == user_id,
                    UserResourceGrantEntity.account_set_id == grant.account_set_id,
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .with_for_update()
                .all()
            )
            grant.is_active = False
            grant.revoked_by = operator_id
            grant.revoked_at = now
            grant.revoke_reason = request.reason
            grant.gmt_modified = now
            for resource_grant in grants:
                self._mark_resource_grant_revoked(
                    resource_grant,
                    operator_id,
                    now,
                    "ACCOUNT_SET_GRANT_REVOKED",
                )
            self._append_audit(
                session,
                action="USER_ACCOUNT_GRANT.REVOKE",
                operator=operator,
                target_type="USER_ACCOUNT_GRANT",
                target_id=grant.grant_id,
                target_account_set_id=grant.account_set_id,
                before=before,
                after={
                    **self._account_grant_snapshot(grant),
                    "reason": request.reason,
                    "revoked_resource_grants": len(grants),
                },
            )
        return impact

    def grant_user_resource(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        operator: Operator,
    ) -> UserResourceGrantResponse:
        operator_id = self._require_system_admin(operator)
        now = _utcnow()
        try:
            with self._dao.session() as session:
                user = self._locked_user(session, user_id)
                if user.role != "query_user" or not user.is_active:
                    raise ManagementValidationError(
                        "Resource grants require an active query user"
                    )
                resource = self._required_resource(session, resource_type, resource_id)
                if not resource.account_set_id:
                    raise ManagementValidationError(
                        "The resource is not assigned to an account set"
                    )
                self._active_account_set(session, resource.account_set_id)
                self._require_active_account_grant(
                    session, user.user_id, resource.account_set_id
                )
                if resource.resource_type == "AGENT":
                    self._validate_agent_grant(session, user.user_id, resource)

                grant = (
                    session.query(UserResourceGrantEntity)
                    .filter(
                        UserResourceGrantEntity.user_id == user.user_id,
                        UserResourceGrantEntity.resource_type == resource.resource_type,
                        UserResourceGrantEntity.resource_id == resource.resource_id,
                    )
                    .with_for_update()
                    .first()
                )
                before = self._resource_grant_snapshot(grant) if grant else None
                if grant is not None and grant.is_active:
                    raise ManagementConflictError(
                        "The user already has this resource grant"
                    )
                if grant is None:
                    grant = UserResourceGrantEntity(
                        grant_id=str(uuid.uuid4()),
                        user_id=user.user_id,
                        resource_type=resource.resource_type,
                        resource_id=resource.resource_id,
                        account_set_id=resource.account_set_id,
                        is_active=True,
                        granted_by=operator_id,
                        gmt_created=now,
                        gmt_modified=now,
                    )
                    session.add(grant)
                else:
                    grant.account_set_id = resource.account_set_id
                    grant.is_active = True
                    grant.granted_by = operator_id
                    grant.revoked_by = None
                    grant.revoked_at = None
                    grant.revoke_reason = None
                    grant.gmt_modified = now
                session.flush()
                self._append_audit(
                    session,
                    action="USER_RESOURCE_GRANT.GRANT",
                    operator=operator,
                    target_type="USER_RESOURCE_GRANT",
                    target_id=grant.grant_id,
                    target_account_set_id=grant.account_set_id,
                    before=before,
                    after=self._resource_grant_snapshot(grant),
                )
                response = UserResourceGrantResponse.model_validate(grant)
        except IntegrityError as exc:
            raise ManagementConflictError(
                "The user already has this resource grant"
            ) from exc
        return response

    def list_user_resource_grants(
        self,
        user_id: str,
        page: int,
        page_size: int,
        operator: Operator,
        resource_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Page[UserResourceGrantResponse]:
        self._require_system_admin(operator)
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            self._existing_user(session, user_id)
            query = session.query(UserResourceGrantEntity).filter(
                UserResourceGrantEntity.user_id == user_id
            )
            if resource_type is not None:
                self._validate_resource_type(resource_type)
                query = query.filter(
                    UserResourceGrantEntity.resource_type == resource_type
                )
            if is_active is not None:
                query = query.filter(UserResourceGrantEntity.is_active.is_(is_active))
            total = query.count()
            entities = (
                query.order_by(
                    UserResourceGrantEntity.gmt_created.desc(),
                    UserResourceGrantEntity.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [
                UserResourceGrantResponse.model_validate(entity) for entity in entities
            ]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def list_available_user_resources(
        self, user_id: str, operator: Operator
    ) -> list[ResourceResponse]:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            user = self._existing_user(session, user_id)
            if user.role != "query_user" or not user.is_active:
                raise ManagementValidationError(
                    "Available resources require an active query user"
                )
            account_set_ids = self._active_user_account_set_ids(session, user_id)
            active_grants = {
                (grant.resource_type, grant.resource_id)
                for grant in session.query(UserResourceGrantEntity)
                .filter(
                    UserResourceGrantEntity.user_id == user_id,
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .all()
            }
            available: list[ResourceResponse] = []
            for resource_type in RESOURCE_DEFINITIONS:
                for resource in list_resources(
                    session,
                    resource_type,
                    account_set_ids=account_set_ids,
                ):
                    if (resource_type, resource.resource_id) in active_grants:
                        continue
                    if resource_type == "AGENT":
                        try:
                            self._validate_agent_grant(session, user_id, resource)
                        except ManagementValidationError:
                            continue
                    available.append(self._resource_response(resource))
        return available

    def revoke_user_resource(
        self,
        user_id: str,
        grant_id: str,
        request: RevokeRequest,
        operator: Operator,
    ) -> UserResourceGrantResponse:
        operator_id = self._require_system_admin(operator)
        now = _utcnow()
        with self._dao.session() as session:
            grant = self._resource_grant(session, user_id, grant_id, for_update=True)
            if not grant.is_active:
                raise ManagementConflictError("The resource grant is not active")
            before = self._resource_grant_snapshot(grant)
            self._mark_resource_grant_revoked(grant, operator_id, now, request.reason)
            revoked_agent_grants = []
            if grant.resource_type != "AGENT":
                try:
                    affected_agent_ids = dependent_agent_ids(
                        session, grant.resource_type, grant.resource_id
                    )
                except ResourceLookupError as exc:
                    raise ManagementValidationError(str(exc)) from exc
                if affected_agent_ids:
                    revoked_agent_grants = (
                        session.query(UserResourceGrantEntity)
                        .filter(
                            UserResourceGrantEntity.user_id == user_id,
                            UserResourceGrantEntity.resource_type == "AGENT",
                            UserResourceGrantEntity.resource_id.in_(affected_agent_ids),
                            UserResourceGrantEntity.is_active.is_(True),
                        )
                        .with_for_update()
                        .all()
                    )
                    for agent_grant in revoked_agent_grants:
                        self._mark_resource_grant_revoked(
                            agent_grant,
                            operator_id,
                            now,
                            "DEPENDENCY_GRANT_REVOKED",
                        )
            self._append_audit(
                session,
                action="USER_RESOURCE_GRANT.REVOKE",
                operator=operator,
                target_type="USER_RESOURCE_GRANT",
                target_id=grant.grant_id,
                target_account_set_id=grant.account_set_id,
                before=before,
                after={
                    **self._resource_grant_snapshot(grant),
                    "revoked_agent_grants": len(revoked_agent_grants),
                },
            )
            response = UserResourceGrantResponse.model_validate(grant)
        return response

    def list_managed_resources(
        self,
        page: int,
        page_size: int,
        operator: Operator,
        resource_type: Optional[str] = None,
        account_set_id: Optional[str] = None,
        unassigned: bool = False,
    ) -> Page[ResourceResponse]:
        self._validate_page(page, page_size)
        if account_set_id is not None and unassigned:
            raise ManagementValidationError(
                "account_set_id and unassigned cannot be combined"
            )
        resource_types = (
            [resource_type] if resource_type is not None else list(RESOURCE_DEFINITIONS)
        )
        with self._dao.session(commit=False) as session:
            scoped_account_sets = self._resource_manager_scope(
                session, operator, resource_types
            )
            counts = {
                current_type: count_resources(
                    session,
                    current_type,
                    account_set_ids=scoped_account_sets,
                    account_set_id=account_set_id,
                    unassigned=unassigned,
                )
                for current_type in resource_types
            }
            total = sum(counts.values())
            remaining_offset = (page - 1) * page_size
            remaining_limit = page_size
            records: list[ResourceRecord] = []
            for current_type in resource_types:
                current_count = counts[current_type]
                if remaining_offset >= current_count:
                    remaining_offset -= current_count
                    continue
                if remaining_limit == 0:
                    break
                records.extend(
                    list_resources(
                        session,
                        current_type,
                        account_set_ids=scoped_account_sets,
                        account_set_id=account_set_id,
                        unassigned=unassigned,
                        offset=remaining_offset,
                        limit=remaining_limit,
                    )
                )
                remaining_limit = page_size - len(records)
                remaining_offset = 0
            items = [self._resource_response(item) for item in records]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def get_resource_impact(
        self,
        resource_type: str,
        resource_id: str,
        new_account_set_id: str,
        operator: Operator,
    ) -> ResourceImpactResponse:
        with self._dao.session(commit=False) as session:
            resource = self._required_resource(session, resource_type, resource_id)
            self._authorize_resource_change(
                session, operator, resource, new_account_set_id
            )
            self._active_account_set(session, new_account_set_id)
            return self._resource_impact(session, resource, new_account_set_id)

    def assign_resource_account(
        self,
        resource_type: str,
        resource_id: str,
        request: AssignResourceAccountRequest,
        operator: Operator,
    ) -> ResourceResponse:
        now = _utcnow()
        with self._dao.session() as session:
            resource = self._required_resource(
                session, resource_type, resource_id, for_update=True
            )
            operator_id = self._authorize_resource_change(
                session, operator, resource, request.account_set_id
            )
            self._active_account_set(session, request.account_set_id)
            impact = self._resource_impact(session, resource, request.account_set_id)
            if (
                not request.confirm_impact
                or request.impact_token != impact.impact_token
            ):
                raise ImpactConfirmationRequiredError(
                    "Resource account-set change requires current impact confirmation"
                )
            if resource.account_set_id == request.account_set_id:
                raise ManagementConflictError(
                    "The resource already belongs to this account set"
                )
            affected_agent_ids = dependent_agent_ids(
                session, resource.resource_type, resource.resource_id
            )
            direct_grants = (
                session.query(UserResourceGrantEntity)
                .filter(
                    UserResourceGrantEntity.resource_type == resource.resource_type,
                    UserResourceGrantEntity.resource_id == resource.resource_id,
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .with_for_update()
                .all()
            )
            agent_grants = []
            if affected_agent_ids:
                agent_grants = (
                    session.query(UserResourceGrantEntity)
                    .filter(
                        UserResourceGrantEntity.resource_type == "AGENT",
                        UserResourceGrantEntity.resource_id.in_(affected_agent_ids),
                        UserResourceGrantEntity.is_active.is_(True),
                    )
                    .with_for_update()
                    .all()
                )
            for grant in [*direct_grants, *agent_grants]:
                self._mark_resource_grant_revoked(
                    grant, operator_id, now, "RESOURCE_ACCOUNT_SET_CHANGED"
                )
            persist_resource_account(
                session,
                resource.resource_type,
                resource.resource_id,
                request.account_set_id,
            )
            after = ResourceRecord(
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
                name=resource.name,
                account_set_id=request.account_set_id,
            )
            self._append_audit(
                session,
                action="RESOURCE.ACCOUNT_SET_CHANGE",
                operator=operator,
                target_type=resource.resource_type,
                target_id=resource.resource_id,
                target_account_set_id=request.account_set_id,
                before=self._resource_response(resource).model_dump(),
                after={
                    **self._resource_response(after).model_dump(),
                    "reason": request.reason,
                    "revoked_resource_grants": len(direct_grants),
                    "revoked_agent_grants": len(agent_grants),
                },
            )
        return self._resource_response(after)

    @staticmethod
    def _existing_user(session, user_id: str) -> UserEntity:
        user = session.query(UserEntity).filter(UserEntity.user_id == user_id).first()
        if user is None:
            raise ManagementNotFoundError("User does not exist")
        return user

    @staticmethod
    def _active_account_set(session, account_set_id: str) -> AccountSetEntity:
        account_set = (
            session.query(AccountSetEntity)
            .filter(
                AccountSetEntity.account_set_id == account_set_id,
                AccountSetEntity.is_active.is_(True),
            )
            .with_for_update()
            .first()
        )
        if account_set is None:
            raise ManagementValidationError("Account set is missing or inactive")
        return account_set

    @staticmethod
    def _account_grant(
        session, user_id: str, grant_id: str, *, for_update: bool = False
    ) -> UserAccountGrantEntity:
        query = session.query(UserAccountGrantEntity).filter(
            UserAccountGrantEntity.grant_id == grant_id,
            UserAccountGrantEntity.user_id == user_id,
        )
        if for_update:
            query = query.with_for_update()
        grant = query.first()
        if grant is None:
            raise ManagementNotFoundError("User account-set grant does not exist")
        return grant

    @staticmethod
    def _resource_grant(
        session, user_id: str, grant_id: str, *, for_update: bool = False
    ) -> UserResourceGrantEntity:
        query = session.query(UserResourceGrantEntity).filter(
            UserResourceGrantEntity.grant_id == grant_id,
            UserResourceGrantEntity.user_id == user_id,
        )
        if for_update:
            query = query.with_for_update()
        grant = query.first()
        if grant is None:
            raise ManagementNotFoundError("User resource grant does not exist")
        return grant

    @staticmethod
    def _require_active_account_grant(
        session, user_id: str, account_set_id: str
    ) -> None:
        exists = (
            session.query(UserAccountGrantEntity.id)
            .filter(
                UserAccountGrantEntity.user_id == user_id,
                UserAccountGrantEntity.account_set_id == account_set_id,
                UserAccountGrantEntity.is_active.is_(True),
            )
            .first()
        )
        if exists is None:
            raise ManagementValidationError(
                "The user does not have the resource's account-set scope"
            )

    @staticmethod
    def _active_user_account_set_ids(session, user_id: str) -> set[str]:
        active_account_sets = (
            session.query(AccountSetEntity.account_set_id)
            .join(
                UserAccountGrantEntity,
                UserAccountGrantEntity.account_set_id
                == AccountSetEntity.account_set_id,
            )
            .filter(
                UserAccountGrantEntity.user_id == user_id,
                UserAccountGrantEntity.is_active.is_(True),
                AccountSetEntity.is_active.is_(True),
            )
            .all()
        )
        return {account_set_id for (account_set_id,) in active_account_sets}

    def _validate_agent_grant(
        self, session, user_id: str, agent: ResourceRecord
    ) -> None:
        try:
            dependencies = agent_dependencies(session, agent.resource_id)
        except ResourceLookupError as exc:
            raise ManagementValidationError(str(exc)) from exc
        for dependency in dependencies:
            if (
                not dependency.account_set_id
                or dependency.account_set_id != agent.account_set_id
            ):
                raise ManagementValidationError(
                    "All protected agent dependencies must belong to the agent's "
                    "account set"
                )
            grant_exists = (
                session.query(UserResourceGrantEntity.id)
                .filter(
                    UserResourceGrantEntity.user_id == user_id,
                    UserResourceGrantEntity.resource_type == dependency.resource_type,
                    UserResourceGrantEntity.resource_id == dependency.resource_id,
                    UserResourceGrantEntity.account_set_id == dependency.account_set_id,
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .first()
            )
            if grant_exists is None:
                raise ManagementValidationError(
                    "The query user must be granted every protected agent dependency"
                )

    def _account_grant_impact(
        self, session, grant: UserAccountGrantEntity
    ) -> RevokeImpactResponse:
        affected = (
            session.query(UserResourceGrantEntity)
            .filter(
                UserResourceGrantEntity.user_id == grant.user_id,
                UserResourceGrantEntity.account_set_id == grant.account_set_id,
                UserResourceGrantEntity.is_active.is_(True),
            )
            .order_by(UserResourceGrantEntity.grant_id)
            .all()
        )
        details = [self._resource_grant_snapshot(item) for item in affected]
        token_data = {
            "grant_id": grant.grant_id,
            "is_active": grant.is_active,
            "gmt_modified": grant.gmt_modified.isoformat(),
            "affected_grant_ids": [item.grant_id for item in affected],
        }
        return RevokeImpactResponse(
            grant_id=grant.grant_id,
            affected_resource_grants=len(affected),
            affected_grants_detail=details,
            impact_token=hashlib.sha256(
                _json_summary(token_data).encode("utf-8")
            ).hexdigest(),
        )

    def _resource_impact(
        self,
        session,
        resource: ResourceRecord,
        new_account_set_id: str,
    ) -> ResourceImpactResponse:
        if resource.resource_type == "AGENT":
            try:
                dependencies = agent_dependencies(session, resource.resource_id)
            except ResourceLookupError as exc:
                raise ManagementValidationError(str(exc)) from exc
            if any(
                dependency.account_set_id != new_account_set_id
                for dependency in dependencies
            ):
                raise ManagementValidationError(
                    "An agent must belong to the same account set as all protected "
                    "dependencies"
                )
        try:
            affected_agent_ids = dependent_agent_ids(
                session, resource.resource_type, resource.resource_id
            )
        except ResourceLookupError as exc:
            raise ManagementValidationError(str(exc)) from exc
        direct_grants = (
            session.query(UserResourceGrantEntity)
            .filter(
                UserResourceGrantEntity.resource_type == resource.resource_type,
                UserResourceGrantEntity.resource_id == resource.resource_id,
                UserResourceGrantEntity.is_active.is_(True),
            )
            .order_by(UserResourceGrantEntity.grant_id)
            .all()
        )
        agent_grants = []
        if affected_agent_ids:
            agent_grants = (
                session.query(UserResourceGrantEntity)
                .filter(
                    UserResourceGrantEntity.resource_type == "AGENT",
                    UserResourceGrantEntity.resource_id.in_(affected_agent_ids),
                    UserResourceGrantEntity.is_active.is_(True),
                )
                .order_by(UserResourceGrantEntity.grant_id)
                .all()
            )
        details = [
            self._resource_grant_snapshot(item)
            for item in [*direct_grants, *agent_grants]
        ]
        token_data = {
            "resource_type": resource.resource_type,
            "resource_id": resource.resource_id,
            "current_account_set_id": resource.account_set_id,
            "new_account_set_id": new_account_set_id,
            "affected_grant_ids": [item["grant_id"] for item in details],
        }
        return ResourceImpactResponse(
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            current_account_set_id=resource.account_set_id,
            new_account_set_id=new_account_set_id,
            affected_resource_grants=len(direct_grants),
            affected_agent_grants=len(agent_grants),
            affected_grants_detail=details,
            impact_token=hashlib.sha256(
                _json_summary(token_data).encode("utf-8")
            ).hexdigest(),
        )

    def _authorize_resource_change(
        self,
        session,
        operator: Operator,
        resource: ResourceRecord,
        new_account_set_id: str,
    ) -> str:
        operator_id = self._require_resource_permission(
            operator, resource.resource_type
        )
        if operator.role == "system_admin":
            return operator_id
        if resource.account_set_id is None:
            raise ManagementValidationError(
                "Only system administrators may assign unowned resources"
            )
        scope = self._active_user_account_set_ids(session, operator_id)
        required_scopes = {new_account_set_id}
        if resource.account_set_id:
            required_scopes.add(resource.account_set_id)
        if not required_scopes.issubset(scope):
            raise ManagementValidationError(
                "Operations administrators may only move resources within their "
                "account-set scope"
            )
        return operator_id

    def _resource_manager_scope(
        self, session, operator: Operator, resource_types: list[str]
    ) -> Optional[set[str]]:
        for resource_type in resource_types:
            self._require_resource_permission(operator, resource_type)
        if operator.role == "system_admin":
            return None
        if not operator.user_id:
            raise ManagementValidationError("An authenticated operator is required")
        return self._active_user_account_set_ids(session, operator.user_id)

    @staticmethod
    def _require_resource_permission(operator: Operator, resource_type: str) -> str:
        AuthorizationMixin._validate_resource_type(resource_type)
        if not operator.user_id or not operator.role:
            raise ManagementValidationError("An authenticated operator is required")
        permission = _RESOURCE_MANAGE_PERMISSIONS[resource_type]
        if permission not in ROLE_PERMISSIONS.get(operator.role, set()):
            raise ManagementValidationError(
                f"The operator lacks {permission} capability"
            )
        return operator.user_id

    @staticmethod
    def _required_resource(
        session,
        resource_type: str,
        resource_id: str,
        *,
        for_update: bool = False,
    ) -> ResourceRecord:
        try:
            resource = get_resource(
                session, resource_type, resource_id, for_update=for_update
            )
        except ResourceLookupError as exc:
            raise ManagementValidationError(str(exc)) from exc
        if resource is None:
            raise ManagementNotFoundError("Resource does not exist")
        return resource

    @staticmethod
    def _validate_resource_type(resource_type: str) -> None:
        if resource_type not in RESOURCE_DEFINITIONS:
            raise ManagementValidationError(
                f"Unsupported resource type: {resource_type}"
            )

    @staticmethod
    def _mark_resource_grant_revoked(
        grant: UserResourceGrantEntity,
        operator_id: str,
        now,
        reason: str,
    ) -> None:
        grant.is_active = False
        grant.revoked_by = operator_id
        grant.revoked_at = now
        grant.revoke_reason = reason
        grant.gmt_modified = now

    @staticmethod
    def _resource_response(resource: ResourceRecord) -> ResourceResponse:
        return ResourceResponse(
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            name=resource.name,
            account_set_id=resource.account_set_id,
        )

    @staticmethod
    def _account_grant_snapshot(
        grant: UserAccountGrantEntity,
    ) -> dict:
        return {
            "grant_id": grant.grant_id,
            "user_id": grant.user_id,
            "account_set_id": grant.account_set_id,
            "is_active": grant.is_active,
            "granted_by": grant.granted_by,
            "revoked_by": grant.revoked_by,
            "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
            "revoke_reason": grant.revoke_reason,
        }

    @staticmethod
    def _resource_grant_snapshot(
        grant: UserResourceGrantEntity,
    ) -> dict:
        return {
            "grant_id": grant.grant_id,
            "user_id": grant.user_id,
            "resource_type": grant.resource_type,
            "resource_id": grant.resource_id,
            "account_set_id": grant.account_set_id,
            "is_active": grant.is_active,
            "granted_by": grant.granted_by,
            "revoked_by": grant.revoked_by,
            "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
            "revoke_reason": grant.revoke_reason,
        }
