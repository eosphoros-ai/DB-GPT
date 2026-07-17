"""Transactional user, account-set, role, and import administration."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from sqlalchemy import column, func, select, table
from sqlalchemy.exc import IntegrityError

from dbgpt_serve.auth.api.schemas import (
    AccountSetCreateRequest,
    AccountSetImpactResponse,
    AccountSetResponse,
    AccountSetUpdateRequest,
    ConfirmImpactRequest,
    ImportBatchRequest,
    ImportBatchResponse,
    ImportCandidateResponse,
    Page,
    RoleResponse,
    UserCreateRequest,
    UserListRequest,
    UserResponse,
    UserUpdateRequest,
)
from dbgpt_serve.auth.constants import ROLE_PERMISSIONS
from dbgpt_serve.auth.models.models import (
    AccountSetEntity,
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
    ManagementNotFoundError,
    ManagementValidationError,
)
from dbgpt_serve.auth.service.importer import LszyzdImporter


class Operator(Protocol):
    """Minimum authenticated operator fields used by management transactions."""

    user_id: Optional[str]
    role: Optional[str]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_summary(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class ManagementMixin:
    """Administration methods mixed into the authentication service."""

    _importer: Optional[LszyzdImporter]

    def create_user(
        self, request: UserCreateRequest, operator: Operator
    ) -> UserResponse:
        operator_id = self._require_system_admin(operator)
        password_hash = self._password_hash_for_create(request)
        now = _utcnow()
        try:
            with self._dao.session() as session:
                if (
                    session.query(UserEntity.id)
                    .filter(UserEntity.login_name == request.login_name)
                    .first()
                    is not None
                ):
                    raise ManagementConflictError("Login name already exists")
                account_sets = self._active_account_sets(
                    session, request.initial_account_set_ids
                )
                user = UserEntity(
                    user_id=str(uuid.uuid4()),
                    login_name=request.login_name,
                    display_name=request.display_name,
                    password_hash=password_hash,
                    role=request.role,
                    is_active=True,
                    created_by=operator_id,
                    gmt_created=now,
                    gmt_modified=now,
                )
                session.add(user)
                session.flush()
                self._add_account_grants(
                    session, user.user_id, account_sets, operator_id
                )
                self._append_audit(
                    session,
                    action="USER.CREATE",
                    operator=operator,
                    target_type="USER",
                    target_id=user.user_id,
                    after={
                        **self._user_snapshot(user),
                        "initial_account_set_ids": sorted(account_sets),
                    },
                )
                response = UserResponse.from_entity(user)
        except IntegrityError as exc:
            raise ManagementConflictError("Login name already exists") from exc
        return response

    def update_user(
        self, user_id: str, request: UserUpdateRequest, operator: Operator
    ) -> UserResponse:
        self._require_system_admin(operator)
        now = _utcnow()
        with self._dao.session() as session:
            user = self._locked_user(session, user_id)
            before = self._user_snapshot(user)
            revoked_resource_grants = 0
            revoked_account_grants = 0

            if request.role is not None and request.role != user.role:
                if not request.confirm_role_change or not request.change_reason:
                    raise ImpactConfirmationRequiredError(
                        "Role changes require confirmation and a reason"
                    )
                if user.role == "system_admin" and request.role != "system_admin":
                    self._assert_admin_can_be_removed(session, user.user_id)
                if user.role == "query_user" and request.role != "query_user":
                    revoked_resource_grants = self._revoke_resource_grants(
                        session, user.user_id, operator.user_id, "ROLE_CHANGED", now
                    )
                if request.role == "system_admin":
                    revoked_account_grants = self._revoke_account_grants(
                        session, user.user_id, operator.user_id, "ROLE_CHANGED", now
                    )
                user.role = request.role

            if request.display_name is not None:
                user.display_name = request.display_name
            user.gmt_modified = now
            after = {
                **self._user_snapshot(user),
                "change_reason": request.change_reason,
                "revoked_resource_grants": revoked_resource_grants,
                "revoked_account_grants": revoked_account_grants,
            }
            self._append_audit(
                session,
                action="USER.ROLE_CHANGE"
                if before["role"] != user.role
                else "USER.UPDATE",
                operator=operator,
                target_type="USER",
                target_id=user.user_id,
                before=before,
                after=after,
            )
            response = UserResponse.from_entity(user)
        return response

    def toggle_user_active(
        self, user_id: str, is_active: bool, operator: Operator
    ) -> UserResponse:
        operator_id = self._require_system_admin(operator)
        now = _utcnow()
        with self._dao.session() as session:
            user = self._locked_user(session, user_id)
            if user.is_active == is_active:
                return UserResponse.from_entity(user)
            before = self._user_snapshot(user)
            revoked_sessions = 0
            if is_active:
                user.is_active = True
                user.disabled_by = None
                user.disabled_at = None
            else:
                if user.role == "system_admin":
                    self._assert_admin_can_be_removed(session, user.user_id)
                user.is_active = False
                user.disabled_by = operator_id
                user.disabled_at = now
                revoked_sessions = self._revoke_sessions(
                    session, user.user_id, operator_id, "USER_DISABLED", now
                )
            user.gmt_modified = now
            self._append_audit(
                session,
                action="USER.ACTIVATE" if is_active else "USER.DEACTIVATE",
                operator=operator,
                target_type="USER",
                target_id=user.user_id,
                before=before,
                after={
                    **self._user_snapshot(user),
                    "revoked_sessions": revoked_sessions,
                },
            )
            response = UserResponse.from_entity(user)
        return response

    def set_password(self, user_id: str, new_password: str, operator: Operator) -> None:
        operator_id = self._require_system_admin(operator)
        try:
            password_hash = self.hash_password(new_password)
        except ValueError as exc:
            raise ManagementValidationError(str(exc)) from exc
        now = _utcnow()
        with self._dao.session() as session:
            user = self._locked_user(session, user_id)
            user.password_hash = password_hash
            user.activation_token = None
            user.activation_token_exp = None
            user.reset_token = None
            user.reset_token_exp = None
            user.login_fail_count = 0
            user.locked_until = None
            user.gmt_modified = now
            revoked_sessions = self._revoke_sessions(
                session, user.user_id, operator_id, "PASSWORD_CHANGED", now
            )
            self._append_audit(
                session,
                action="USER.SET_PASSWORD",
                operator=operator,
                target_type="USER",
                target_id=user.user_id,
                after={"password_changed": True, "revoked_sessions": revoked_sessions},
            )

    def get_managed_user(self, user_id: str, operator: Operator) -> UserResponse:
        self._require_system_admin(operator)
        user = self._dao.get_by_user_id(user_id)
        if user is None:
            raise ManagementNotFoundError("User does not exist")
        return UserResponse.from_entity(user)

    def list_users(
        self,
        filters: UserListRequest,
        page: int,
        page_size: int,
        operator: Operator,
    ) -> Page[UserResponse]:
        self._require_system_admin(operator)
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            query = session.query(UserEntity)
            if filters.login_name_like:
                query = query.filter(
                    UserEntity.login_name.contains(
                        filters.login_name_like, autoescape=True
                    )
                )
            if filters.display_name_like:
                query = query.filter(
                    UserEntity.display_name.contains(
                        filters.display_name_like, autoescape=True
                    )
                )
            if filters.role:
                query = query.filter(UserEntity.role == filters.role)
            if filters.is_active is not None:
                query = query.filter(UserEntity.is_active.is_(filters.is_active))
            total = query.count()
            entities = (
                query.order_by(UserEntity.gmt_created.desc(), UserEntity.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [UserResponse.from_entity(entity) for entity in entities]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def list_roles(self, operator: Operator) -> list[RoleResponse]:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            counts = dict(
                session.query(UserEntity.role, func.count())
                .group_by(UserEntity.role)
                .all()
            )
        return [
            RoleResponse(
                role=role,
                permissions=sorted(permissions),
                user_count=counts.get(role, 0),
            )
            for role, permissions in ROLE_PERMISSIONS.items()
        ]

    def create_account_set(
        self, request: AccountSetCreateRequest, operator: Operator
    ) -> AccountSetResponse:
        operator_id = self._require_system_admin(operator)
        now = _utcnow()
        try:
            with self._dao.session() as session:
                if (
                    session.query(AccountSetEntity.id)
                    .filter(AccountSetEntity.name == request.name)
                    .first()
                    is not None
                ):
                    raise ManagementConflictError("Account-set name already exists")
                account_set = AccountSetEntity(
                    account_set_id=str(uuid.uuid4()),
                    name=request.name,
                    description=request.description,
                    is_active=True,
                    created_by=operator_id,
                    gmt_created=now,
                    gmt_modified=now,
                )
                session.add(account_set)
                session.flush()
                self._append_audit(
                    session,
                    action="ACCOUNT_SET.CREATE",
                    operator=operator,
                    target_type="ACCOUNT_SET",
                    target_id=account_set.account_set_id,
                    target_account_set_id=account_set.account_set_id,
                    after=self._account_set_snapshot(account_set),
                )
                response = AccountSetResponse.model_validate(account_set)
        except IntegrityError as exc:
            raise ManagementConflictError("Account-set name already exists") from exc
        return response

    def update_account_set(
        self,
        account_set_id: str,
        request: AccountSetUpdateRequest,
        operator: Operator,
    ) -> AccountSetResponse:
        self._require_system_admin(operator)
        now = _utcnow()
        try:
            with self._dao.session() as session:
                account_set = self._locked_account_set(session, account_set_id)
                before = self._account_set_snapshot(account_set)
                if request.name is not None and request.name != account_set.name:
                    if (
                        session.query(AccountSetEntity.id)
                        .filter(
                            AccountSetEntity.name == request.name,
                            AccountSetEntity.id != account_set.id,
                        )
                        .first()
                        is not None
                    ):
                        raise ManagementConflictError("Account-set name already exists")
                    account_set.name = request.name
                if "description" in request.model_fields_set:
                    account_set.description = request.description
                account_set.gmt_modified = now
                self._append_audit(
                    session,
                    action="ACCOUNT_SET.UPDATE",
                    operator=operator,
                    target_type="ACCOUNT_SET",
                    target_id=account_set.account_set_id,
                    target_account_set_id=account_set.account_set_id,
                    before=before,
                    after=self._account_set_snapshot(account_set),
                )
                response = AccountSetResponse.model_validate(account_set)
        except IntegrityError as exc:
            raise ManagementConflictError("Account-set name already exists") from exc
        return response

    def get_account_set(
        self, account_set_id: str, operator: Operator
    ) -> AccountSetResponse:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            account_set = (
                session.query(AccountSetEntity)
                .filter(AccountSetEntity.account_set_id == account_set_id)
                .first()
            )
            if account_set is None:
                raise ManagementNotFoundError("Account set does not exist")
            return AccountSetResponse.model_validate(account_set)

    def list_account_sets(
        self,
        page: int,
        page_size: int,
        operator: Operator,
        name_like: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Page[AccountSetResponse]:
        self._require_system_admin(operator)
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            query = session.query(AccountSetEntity)
            if name_like:
                query = query.filter(
                    AccountSetEntity.name.contains(name_like, autoescape=True)
                )
            if is_active is not None:
                query = query.filter(AccountSetEntity.is_active.is_(is_active))
            total = query.count()
            entities = (
                query.order_by(
                    AccountSetEntity.gmt_created.desc(), AccountSetEntity.id.desc()
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [AccountSetResponse.model_validate(entity) for entity in entities]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def get_account_set_impact(
        self, account_set_id: str, operator: Operator
    ) -> AccountSetImpactResponse:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            account_set = (
                session.query(AccountSetEntity)
                .filter(AccountSetEntity.account_set_id == account_set_id)
                .first()
            )
            if account_set is None:
                raise ManagementNotFoundError("Account set does not exist")
            return self._account_set_impact(session, account_set)

    def toggle_account_set_active(
        self,
        account_set_id: str,
        is_active: bool,
        operator: Operator,
        confirmation: Optional[ConfirmImpactRequest] = None,
    ) -> AccountSetResponse:
        self._require_system_admin(operator)
        now = _utcnow()
        with self._dao.session() as session:
            account_set = self._locked_account_set(session, account_set_id)
            if account_set.is_active == is_active:
                return AccountSetResponse.model_validate(account_set)
            before = self._account_set_snapshot(account_set)
            after_extra: dict[str, Any] = {}
            if not is_active:
                impact = self._account_set_impact(session, account_set)
                if (
                    confirmation is None
                    or not confirmation.confirm_impact
                    or confirmation.impact_token != impact.impact_token
                ):
                    raise ImpactConfirmationRequiredError(
                        "Account-set deactivation requires current impact confirmation"
                    )
                after_extra = {
                    "reason": confirmation.reason,
                    "impact": impact.model_dump(exclude={"impact_token"}),
                }
            account_set.is_active = is_active
            account_set.gmt_modified = now
            self._append_audit(
                session,
                action="ACCOUNT_SET.ACTIVATE"
                if is_active
                else "ACCOUNT_SET.DEACTIVATE",
                operator=operator,
                target_type="ACCOUNT_SET",
                target_id=account_set.account_set_id,
                target_account_set_id=account_set.account_set_id,
                before=before,
                after={**self._account_set_snapshot(account_set), **after_extra},
            )
            response = AccountSetResponse.model_validate(account_set)
        return response

    def preview_import_candidates(
        self, operator: Operator, limit: int = 100
    ) -> list[ImportCandidateResponse]:
        self._require_system_admin(operator)
        return self._get_importer().preview(limit=limit)

    def create_from_import(
        self, request: ImportBatchRequest, operator: Operator
    ) -> ImportBatchResponse:
        operator_id = self._require_system_admin(operator)
        importer = self._get_importer()
        candidates = {item.employee_no: item for item in importer.preview(limit=100)}
        password_hashes: dict[str, str] = {}
        for item in request.users:
            try:
                password_hashes[item.employee_no] = self.hash_password(
                    item.initial_password.get_secret_value()
                )
            except ValueError as exc:
                raise ManagementValidationError(str(exc)) from exc

        now = _utcnow()
        batch_id = str(uuid.uuid4())
        selected_summary: list[dict] = []
        result_summary: list[dict] = []
        created_count = 0
        skipped_count = 0
        try:
            with self._dao.session() as session:
                previous_employee_numbers = self._previous_import_employee_numbers(
                    session
                )
                for item in request.users:
                    candidate = candidates.get(item.employee_no)
                    selected_summary.append(
                        {
                            **(candidate.model_dump() if candidate else {}),
                            "employee_no": item.employee_no,
                            "login_name": item.login_name,
                            "role": item.role,
                            "initial_account_set_ids": sorted(
                                set(item.initial_account_set_ids)
                            ),
                            "duplicate_import": item.employee_no
                            in previous_employee_numbers,
                        }
                    )
                    skip_reason: Optional[str] = None
                    if candidate is None:
                        skip_reason = "SOURCE_RECORD_MISSING"
                    elif item.employee_no in previous_employee_numbers:
                        skip_reason = "SOURCE_RECORD_ALREADY_IMPORTED"
                    elif (
                        session.query(UserEntity.id)
                        .filter(UserEntity.login_name == item.login_name)
                        .first()
                        is not None
                    ):
                        skip_reason = "LOGIN_NAME_EXISTS"

                    if skip_reason:
                        skipped_count += 1
                        result_summary.append(
                            {
                                "employee_no": item.employee_no,
                                "login_name": item.login_name,
                                "result": "skipped",
                                "reason": skip_reason,
                            }
                        )
                        continue

                    account_sets = self._active_account_sets(
                        session, item.initial_account_set_ids
                    )
                    user = UserEntity(
                        user_id=str(uuid.uuid4()),
                        login_name=item.login_name,
                        display_name=candidate.name,
                        password_hash=password_hashes[item.employee_no],
                        role=item.role,
                        is_active=True,
                        created_by=operator_id,
                        gmt_created=now,
                        gmt_modified=now,
                    )
                    session.add(user)
                    session.flush()
                    self._add_account_grants(
                        session, user.user_id, account_sets, operator_id
                    )
                    self._append_audit(
                        session,
                        action="USER.IMPORT_CREATE",
                        operator=operator,
                        target_type="USER",
                        target_id=user.user_id,
                        after={
                            **self._user_snapshot(user),
                            "source": importer.source_name,
                            "source_employee_no": item.employee_no,
                        },
                    )
                    created_count += 1
                    result_summary.append(
                        {
                            "employee_no": item.employee_no,
                            "login_name": item.login_name,
                            "user_id": user.user_id,
                            "result": "created",
                        }
                    )

                batch = ImportBatchEntity(
                    batch_id=batch_id,
                    operator_user_id=operator_id,
                    source_name=importer.source_name,
                    selected_count=len(request.users),
                    created_count=created_count,
                    skipped_count=skipped_count,
                    selected_summary=_json_summary(selected_summary),
                    result_summary=_json_summary(result_summary),
                    gmt_created=now,
                )
                session.add(batch)
                session.flush()
                self._append_audit(
                    session,
                    action="IMPORT.BATCH_CREATE",
                    operator=operator,
                    target_type="IMPORT_BATCH",
                    target_id=batch.batch_id,
                    after={
                        "source_name": batch.source_name,
                        "selected_count": batch.selected_count,
                        "created_count": batch.created_count,
                        "skipped_count": batch.skipped_count,
                    },
                )
                response = ImportBatchResponse.from_entity(batch)
        except IntegrityError as exc:
            raise ManagementConflictError(
                "Import conflicted with a concurrently created account"
            ) from exc
        return response

    def list_import_batches(
        self, page: int, page_size: int, operator: Operator
    ) -> Page[ImportBatchResponse]:
        self._require_system_admin(operator)
        self._validate_page(page, page_size)
        with self._dao.session(commit=False) as session:
            query = session.query(ImportBatchEntity)
            total = query.count()
            entities = (
                query.order_by(
                    ImportBatchEntity.gmt_created.desc(), ImportBatchEntity.id.desc()
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = [ImportBatchResponse.from_entity(entity) for entity in entities]
        return Page(items=items, total=total, page=page, page_size=page_size)

    def get_import_batch(
        self, batch_id: str, operator: Operator
    ) -> ImportBatchResponse:
        self._require_system_admin(operator)
        with self._dao.session(commit=False) as session:
            entity = (
                session.query(ImportBatchEntity)
                .filter(ImportBatchEntity.batch_id == batch_id)
                .first()
            )
            if entity is None:
                raise ManagementNotFoundError("Import batch does not exist")
            return ImportBatchResponse.from_entity(entity)

    def _get_importer(self) -> LszyzdImporter:
        if self._importer is not None:
            return self._importer
        if self.system_app is None:
            raise ImportSourceError("SystemApp is not initialized")
        from dbgpt_serve.datasource.manages.connector_manager import ConnectorManager

        manager = ConnectorManager.get_instance(self.system_app)
        self._importer = LszyzdImporter(
            manager,
            datasource_name=self._config.lszyzd_datasource,
            table_name=self._config.lszyzd_table,
        )
        return self._importer

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ManagementValidationError(
                "page must be at least 1 and page_size must be between 1 and 100"
            )

    @staticmethod
    def _require_system_admin(operator: Operator) -> str:
        if operator.role != "system_admin" or not operator.user_id:
            raise ManagementValidationError("A system administrator is required")
        return operator.user_id

    @staticmethod
    def _locked_user(session, user_id: str) -> UserEntity:
        user = (
            session.query(UserEntity)
            .filter(UserEntity.user_id == user_id)
            .with_for_update()
            .first()
        )
        if user is None:
            raise ManagementNotFoundError("User does not exist")
        return user

    @staticmethod
    def _locked_account_set(session, account_set_id: str) -> AccountSetEntity:
        account_set = (
            session.query(AccountSetEntity)
            .filter(AccountSetEntity.account_set_id == account_set_id)
            .with_for_update()
            .first()
        )
        if account_set is None:
            raise ManagementNotFoundError("Account set does not exist")
        return account_set

    @staticmethod
    def _assert_admin_can_be_removed(session, target_user_id: str) -> None:
        active_admins = (
            session.query(UserEntity)
            .filter(
                UserEntity.role == "system_admin",
                UserEntity.is_active.is_(True),
            )
            .order_by(UserEntity.id)
            .with_for_update()
            .all()
        )
        if len(active_admins) <= 1 and any(
            user.user_id == target_user_id for user in active_admins
        ):
            raise ManagementConflictError(
                "The last active system administrator cannot be disabled or demoted"
            )

    def _password_hash_for_create(self, request: UserCreateRequest) -> str:
        if request.send_activation:
            raise ManagementValidationError(
                "Activation delivery is not configured; provide an initial password"
            )
        if request.initial_password is None:
            raise ManagementValidationError("An initial password is required")
        try:
            return self.hash_password(request.initial_password.get_secret_value())
        except ValueError as exc:
            raise ManagementValidationError(str(exc)) from exc

    @staticmethod
    def _active_account_sets(session, account_set_ids: list[str]) -> dict[str, Any]:
        normalized_ids = list(dict.fromkeys(account_set_ids))
        if len(normalized_ids) != len(account_set_ids) or any(
            not account_set_id.strip() for account_set_id in normalized_ids
        ):
            raise ManagementValidationError(
                "Initial account-set IDs must be non-blank and unique"
            )
        if not normalized_ids:
            return {}
        entities = (
            session.query(AccountSetEntity)
            .filter(
                AccountSetEntity.account_set_id.in_(normalized_ids),
                AccountSetEntity.is_active.is_(True),
            )
            .all()
        )
        by_id = {entity.account_set_id: entity for entity in entities}
        missing = set(normalized_ids) - set(by_id)
        if missing:
            raise ManagementValidationError(
                f"Account sets are missing or inactive: {sorted(missing)}"
            )
        return by_id

    @staticmethod
    def _add_account_grants(
        session,
        user_id: str,
        account_sets: dict[str, AccountSetEntity],
        operator_id: str,
    ) -> None:
        now = _utcnow()
        for account_set_id in account_sets:
            session.add(
                UserAccountGrantEntity(
                    grant_id=str(uuid.uuid4()),
                    user_id=user_id,
                    account_set_id=account_set_id,
                    is_active=True,
                    granted_by=operator_id,
                    gmt_created=now,
                    gmt_modified=now,
                )
            )

    @staticmethod
    def _revoke_resource_grants(
        session,
        user_id: str,
        operator_id: Optional[str],
        reason: str,
        now: datetime,
    ) -> int:
        grants = (
            session.query(UserResourceGrantEntity)
            .filter(
                UserResourceGrantEntity.user_id == user_id,
                UserResourceGrantEntity.is_active.is_(True),
            )
            .with_for_update()
            .all()
        )
        for grant in grants:
            grant.is_active = False
            grant.revoked_by = operator_id
            grant.revoked_at = now
            grant.revoke_reason = reason
            grant.gmt_modified = now
        return len(grants)

    @staticmethod
    def _revoke_account_grants(
        session,
        user_id: str,
        operator_id: Optional[str],
        reason: str,
        now: datetime,
    ) -> int:
        grants = (
            session.query(UserAccountGrantEntity)
            .filter(
                UserAccountGrantEntity.user_id == user_id,
                UserAccountGrantEntity.is_active.is_(True),
            )
            .with_for_update()
            .all()
        )
        for grant in grants:
            grant.is_active = False
            grant.revoked_by = operator_id
            grant.revoked_at = now
            grant.revoke_reason = reason
            grant.gmt_modified = now
        return len(grants)

    @staticmethod
    def _revoke_sessions(
        session,
        user_id: str,
        operator_id: str,
        reason: str,
        now: datetime,
    ) -> int:
        sessions = (
            session.query(SessionEntity)
            .filter(
                SessionEntity.user_id == user_id,
                SessionEntity.revoked_at.is_(None),
            )
            .with_for_update()
            .all()
        )
        for auth_session in sessions:
            auth_session.revoked_at = now
            auth_session.revoked_by = operator_id
            auth_session.revoke_reason = reason
            auth_session.gmt_modified = now
        return len(sessions)

    @staticmethod
    def _previous_import_employee_numbers(session) -> set[str]:
        employee_numbers: set[str] = set()
        summaries = session.query(ImportBatchEntity.result_summary).all()
        for (summary,) in summaries:
            try:
                items = json.loads(summary or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            for item in items if isinstance(items, list) else []:
                if (
                    isinstance(item, dict)
                    and item.get("result") == "created"
                    and item.get("employee_no")
                ):
                    employee_numbers.add(str(item["employee_no"]))
        return employee_numbers

    def _account_set_impact(
        self, session, account_set: AccountSetEntity
    ) -> AccountSetImpactResponse:
        user_grant_count = (
            session.query(UserAccountGrantEntity.id)
            .filter(
                UserAccountGrantEntity.account_set_id == account_set.account_set_id,
                UserAccountGrantEntity.is_active.is_(True),
            )
            .count()
        )
        resource_grant_count = (
            session.query(UserResourceGrantEntity.id)
            .filter(
                UserResourceGrantEntity.account_set_id == account_set.account_set_id,
                UserResourceGrantEntity.is_active.is_(True),
            )
            .count()
        )
        resource_count = 0
        for table_name in ("connect_config", "knowledge_space", "gpts_app"):
            resource_table = table(table_name, column("account_set_id"))
            resource_count += session.execute(
                select(func.count())
                .select_from(resource_table)
                .where(resource_table.c.account_set_id == account_set.account_set_id)
            ).scalar_one()
        token_data = {
            "account_set_id": account_set.account_set_id,
            "is_active": account_set.is_active,
            "gmt_modified": account_set.gmt_modified.isoformat(),
            "user_grant_count": user_grant_count,
            "resource_grant_count": resource_grant_count,
            "resource_count": resource_count,
        }
        impact_token = hashlib.sha256(_json_summary(token_data).encode()).hexdigest()
        return AccountSetImpactResponse(
            account_set_id=account_set.account_set_id,
            user_grant_count=user_grant_count,
            resource_grant_count=resource_grant_count,
            resource_count=resource_count,
            impact_token=impact_token,
        )

    def _append_audit(
        self,
        session,
        action: str,
        operator: Operator,
        target_type: str,
        target_id: Optional[str],
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        target_account_set_id: Optional[str] = None,
    ) -> None:
        event: AuditEventEntity = self._audit_event(
            action=action,
            result="success",
            operator_user_id=operator.user_id,
            operator_role=operator.role,
            target_type=target_type,
            target_id=target_id,
            source_ip=getattr(operator, "source_ip", "") or "",
            user_agent=getattr(operator, "user_agent", "") or "",
        )
        event.request_id = getattr(operator, "request_id", None)
        event.target_account_set_id = target_account_set_id
        event.before_snapshot = _json_summary(before) if before is not None else None
        event.after_snapshot = _json_summary(after) if after is not None else None
        session.add(event)

    @staticmethod
    def _user_snapshot(user: UserEntity) -> dict[str, Any]:
        return {
            "user_id": user.user_id,
            "login_name": user.login_name,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
            "disabled_at": user.disabled_at.isoformat() if user.disabled_at else None,
        }

    @staticmethod
    def _account_set_snapshot(account_set: AccountSetEntity) -> dict[str, Any]:
        return {
            "account_set_id": account_set.account_set_id,
            "name": account_set.name,
            "description": account_set.description,
            "is_active": account_set.is_active,
        }
