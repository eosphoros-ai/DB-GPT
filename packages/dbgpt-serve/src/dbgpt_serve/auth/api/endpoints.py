"""Authentication endpoints for the administration API."""

from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from starlette.concurrency import run_in_threadpool

from dbgpt.core.schema.api import Result
from dbgpt_serve.auth.api.schemas import (
    AccountSetCreateRequest,
    AccountSetImpactResponse,
    AccountSetResponse,
    AccountSetUpdateRequest,
    AssignResourceAccountRequest,
    ConfirmImpactRequest,
    ConfirmRevokeRequest,
    ImportBatchRequest,
    ImportBatchResponse,
    ImportCandidateResponse,
    LoginRequest,
    LoginResponse,
    Page,
    ResourceImpactResponse,
    ResourceResponse,
    ResourceTypeName,
    RevokeImpactResponse,
    RevokeRequest,
    RoleName,
    RoleResponse,
    SetPasswordRequest,
    UserAccountGrantRequest,
    UserAccountGrantResponse,
    UserCreateRequest,
    UserListRequest,
    UserResourceGrantRequest,
    UserResourceGrantResponse,
    UserResponse,
    UserUpdateRequest,
)
from dbgpt_serve.auth.constants import ROLE_PERMISSIONS
from dbgpt_serve.auth.service.errors import (
    ImpactConfirmationRequiredError,
    ImportSourceError,
    ManagementConflictError,
    ManagementError,
    ManagementNotFoundError,
    ManagementValidationError,
)
from dbgpt_serve.auth.service.service import (
    AuthConfigurationError,
    AuthenticationError,
    Service,
    get_auth_service,
)
from dbgpt_serve.utils.auth import UserRequest, get_current_user, require_permission


def _prevent_admin_response_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(dependencies=[Depends(_prevent_admin_response_caching)])


async def _require_resource_manager(
    user: UserRequest = Depends(get_current_user),
) -> UserRequest:
    permissions = ROLE_PERMISSIONS.get(user.role or "", set())
    if not permissions.intersection(
        {"DATASOURCE_MANAGE", "KNOWLEDGE_BASE_MANAGE", "AGENT_MANAGE"}
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return user


async def _run_management(method: Callable, *args):
    try:
        return await run_in_threadpool(method, *args)
    except ManagementNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except (ImpactConfirmationRequiredError, ManagementConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ManagementValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ManagementError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post("/auth/login", response_model=Result[LoginResponse])
async def login(
    login_request: LoginRequest,
    request: Request,
    response: Response,
    service: Service = Depends(get_auth_service),
) -> Result[LoginResponse]:
    """Authenticate credentials and set the secure session cookie."""
    source_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    try:
        token, user = await run_in_threadpool(
            service.login,
            login_request.login_name,
            login_request.password,
            source_ip,
            user_agent,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login name or password",
        ) from exc
    except AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc

    response.set_cookie(
        key="dbgpt_session",
        value=token,
        max_age=service.config.jwt_absolute_expire_minutes * 60,
        path="/",
        secure=service.config.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key="dbgpt_csrf",
        value=service.csrf_token(token),
        max_age=service.config.jwt_absolute_expire_minutes * 60,
        path="/",
        secure=service.config.cookie_secure,
        httponly=False,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return Result.succ(LoginResponse(access_token=token, user=user))


@router.post("/auth/logout", response_model=Result[None])
async def logout(
    response: Response,
    user: UserRequest = Depends(get_current_user),
    service: Service = Depends(get_auth_service),
) -> Result[None]:
    """Revoke the current server-side session and clear its cookie."""
    if not user.user_id or not user.session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    await run_in_threadpool(service.logout, user.user_id, user.session_id)
    response.delete_cookie(
        key="dbgpt_session",
        path="/",
        secure=service.config.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key="dbgpt_csrf",
        path="/",
        secure=service.config.cookie_secure,
        httponly=False,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return Result.succ(None)


@router.get("/auth/me", response_model=Result[UserResponse])
async def current_user(
    response: Response,
    user: UserRequest = Depends(get_current_user),
) -> Result[UserResponse]:
    """Return the current database-backed user identity."""
    if (
        not user.user_id
        or not user.login_name
        or not user.display_name
        or not user.role
        or user.gmt_created is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    response.headers["Cache-Control"] = "no-store"
    return Result.succ(
        UserResponse(
            user_id=user.user_id,
            login_name=user.login_name,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            gmt_created=user.gmt_created,
            disabled_at=user.disabled_at,
        )
    )


@router.get("/users", response_model=Result[Page[UserResponse]])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    login_name_like: Optional[str] = Query(default=None, max_length=128),
    display_name_like: Optional[str] = Query(default=None, max_length=255),
    role: Optional[RoleName] = None,
    is_active: Optional[bool] = None,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[Page[UserResponse]]:
    filters = UserListRequest(
        login_name_like=login_name_like,
        display_name_like=display_name_like,
        role=role,
        is_active=is_active,
    )
    result = await _run_management(
        service.list_users, filters, page, page_size, operator
    )
    return Result.succ(result)


@router.post(
    "/users", response_model=Result[UserResponse], status_code=status.HTTP_201_CREATED
)
async def create_user(
    request: UserCreateRequest,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResponse]:
    result = await _run_management(service.create_user, request, operator)
    return Result.succ(result)


@router.get("/users/{user_id}", response_model=Result[UserResponse])
async def get_user(
    user_id: str,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResponse]:
    result = await _run_management(service.get_managed_user, user_id, operator)
    return Result.succ(result)


@router.patch("/users/{user_id}", response_model=Result[UserResponse])
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResponse]:
    result = await _run_management(service.update_user, user_id, request, operator)
    return Result.succ(result)


@router.post("/users/{user_id}/activate", response_model=Result[UserResponse])
async def activate_user(
    user_id: str,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResponse]:
    result = await _run_management(service.toggle_user_active, user_id, True, operator)
    return Result.succ(result)


@router.post("/users/{user_id}/deactivate", response_model=Result[UserResponse])
async def deactivate_user(
    user_id: str,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResponse]:
    result = await _run_management(service.toggle_user_active, user_id, False, operator)
    return Result.succ(result)


@router.post("/users/{user_id}/set-password", response_model=Result[None])
async def set_user_password(
    user_id: str,
    request: SetPasswordRequest,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[None]:
    await _run_management(
        service.set_password,
        user_id,
        request.new_password.get_secret_value(),
        operator,
    )
    return Result.succ(None)


@router.get("/roles", response_model=Result[list[RoleResponse]])
async def list_roles(
    operator: UserRequest = Depends(require_permission("ROLE_READ")),
    service: Service = Depends(get_auth_service),
) -> Result[list[RoleResponse]]:
    result = await _run_management(service.list_roles, operator)
    return Result.succ(result)


@router.get("/roles/{role}/users", response_model=Result[Page[UserResponse]])
async def list_role_users(
    role: RoleName,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    operator: UserRequest = Depends(require_permission("ROLE_READ")),
    service: Service = Depends(get_auth_service),
) -> Result[Page[UserResponse]]:
    result = await _run_management(
        service.list_users,
        UserListRequest(role=role),
        page,
        page_size,
        operator,
    )
    return Result.succ(result)


@router.get("/account-sets", response_model=Result[Page[AccountSetResponse]])
async def list_account_sets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    name_like: Optional[str] = Query(default=None, max_length=255),
    is_active: Optional[bool] = None,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[Page[AccountSetResponse]]:
    result = await _run_management(
        service.list_account_sets,
        page,
        page_size,
        operator,
        name_like,
        is_active,
    )
    return Result.succ(result)


@router.post(
    "/account-sets",
    response_model=Result[AccountSetResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_account_set(
    request: AccountSetCreateRequest,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[AccountSetResponse]:
    result = await _run_management(service.create_account_set, request, operator)
    return Result.succ(result)


@router.get("/account-sets/{account_set_id}", response_model=Result[AccountSetResponse])
async def get_account_set(
    account_set_id: str,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[AccountSetResponse]:
    result = await _run_management(service.get_account_set, account_set_id, operator)
    return Result.succ(result)


@router.patch(
    "/account-sets/{account_set_id}", response_model=Result[AccountSetResponse]
)
async def update_account_set(
    account_set_id: str,
    request: AccountSetUpdateRequest,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[AccountSetResponse]:
    result = await _run_management(
        service.update_account_set, account_set_id, request, operator
    )
    return Result.succ(result)


@router.get(
    "/account-sets/{account_set_id}/impact",
    response_model=Result[AccountSetImpactResponse],
)
async def get_account_set_impact(
    account_set_id: str,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[AccountSetImpactResponse]:
    result = await _run_management(
        service.get_account_set_impact, account_set_id, operator
    )
    return Result.succ(result)


@router.post(
    "/account-sets/{account_set_id}/activate",
    response_model=Result[AccountSetResponse],
)
async def activate_account_set(
    account_set_id: str,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[AccountSetResponse]:
    result = await _run_management(
        service.toggle_account_set_active, account_set_id, True, operator, None
    )
    return Result.succ(result)


@router.post(
    "/account-sets/{account_set_id}/deactivate",
    response_model=Result[AccountSetResponse],
)
async def deactivate_account_set(
    account_set_id: str,
    request: ConfirmImpactRequest,
    operator: UserRequest = Depends(require_permission("ACCOUNT_SET_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[AccountSetResponse]:
    result = await _run_management(
        service.toggle_account_set_active,
        account_set_id,
        False,
        operator,
        request,
    )
    return Result.succ(result)


@router.get(
    "/users/{user_id}/account-grants",
    response_model=Result[Page[UserAccountGrantResponse]],
)
async def list_user_account_grants(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_active: Optional[bool] = None,
    operator: UserRequest = Depends(require_permission("USER_ACCOUNT_SET_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[Page[UserAccountGrantResponse]]:
    result = await _run_management(
        service.list_user_account_grants,
        user_id,
        page,
        page_size,
        operator,
        is_active,
    )
    return Result.succ(result)


@router.post(
    "/users/{user_id}/account-grants",
    response_model=Result[UserAccountGrantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def grant_user_account(
    user_id: str,
    request: UserAccountGrantRequest,
    operator: UserRequest = Depends(require_permission("USER_ACCOUNT_SET_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[UserAccountGrantResponse]:
    result = await _run_management(
        service.grant_user_account,
        user_id,
        request.account_set_id,
        operator,
    )
    return Result.succ(result)


@router.get(
    "/users/{user_id}/account-grants/{grant_id}/impact",
    response_model=Result[RevokeImpactResponse],
)
async def get_user_account_revoke_impact(
    user_id: str,
    grant_id: str,
    operator: UserRequest = Depends(require_permission("USER_ACCOUNT_SET_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[RevokeImpactResponse]:
    result = await _run_management(
        service.get_user_account_revoke_impact,
        user_id,
        grant_id,
        operator,
    )
    return Result.succ(result)


@router.delete(
    "/users/{user_id}/account-grants/{grant_id}",
    response_model=Result[RevokeImpactResponse],
)
async def revoke_user_account(
    user_id: str,
    grant_id: str,
    request: ConfirmRevokeRequest,
    operator: UserRequest = Depends(require_permission("USER_ACCOUNT_SET_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[RevokeImpactResponse]:
    result = await _run_management(
        service.revoke_user_account,
        user_id,
        grant_id,
        request,
        operator,
    )
    return Result.succ(result)


@router.get(
    "/users/{user_id}/resource-grants",
    response_model=Result[Page[UserResourceGrantResponse]],
)
async def list_user_resource_grants(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    resource_type: Optional[ResourceTypeName] = None,
    is_active: Optional[bool] = None,
    operator: UserRequest = Depends(require_permission("USER_RESOURCE_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[Page[UserResourceGrantResponse]]:
    result = await _run_management(
        service.list_user_resource_grants,
        user_id,
        page,
        page_size,
        operator,
        resource_type,
        is_active,
    )
    return Result.succ(result)


@router.get(
    "/users/{user_id}/resource-grants/available",
    response_model=Result[list[ResourceResponse]],
)
async def list_available_user_resources(
    user_id: str,
    operator: UserRequest = Depends(require_permission("USER_RESOURCE_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[list[ResourceResponse]]:
    result = await _run_management(
        service.list_available_user_resources, user_id, operator
    )
    return Result.succ(result)


@router.post(
    "/users/{user_id}/resource-grants",
    response_model=Result[UserResourceGrantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def grant_user_resource(
    user_id: str,
    request: UserResourceGrantRequest,
    operator: UserRequest = Depends(require_permission("USER_RESOURCE_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResourceGrantResponse]:
    result = await _run_management(
        service.grant_user_resource,
        user_id,
        request.resource_type,
        request.resource_id,
        operator,
    )
    return Result.succ(result)


@router.delete(
    "/users/{user_id}/resource-grants/{grant_id}",
    response_model=Result[UserResourceGrantResponse],
)
async def revoke_user_resource(
    user_id: str,
    grant_id: str,
    request: RevokeRequest,
    operator: UserRequest = Depends(require_permission("USER_RESOURCE_GRANT")),
    service: Service = Depends(get_auth_service),
) -> Result[UserResourceGrantResponse]:
    result = await _run_management(
        service.revoke_user_resource,
        user_id,
        grant_id,
        request,
        operator,
    )
    return Result.succ(result)


@router.get("/resources", response_model=Result[Page[ResourceResponse]])
async def list_managed_resources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    resource_type: Optional[ResourceTypeName] = None,
    account_set_id: Optional[str] = Query(default=None, max_length=128),
    unassigned: bool = False,
    operator: UserRequest = Depends(_require_resource_manager),
    service: Service = Depends(get_auth_service),
) -> Result[Page[ResourceResponse]]:
    result = await _run_management(
        service.list_managed_resources,
        page,
        page_size,
        operator,
        resource_type,
        account_set_id,
        unassigned,
    )
    return Result.succ(result)


@router.get(
    "/resources/{resource_type}/{resource_id}/impact",
    response_model=Result[ResourceImpactResponse],
)
async def get_resource_impact(
    resource_type: ResourceTypeName,
    resource_id: str,
    new_account_set_id: str = Query(min_length=1, max_length=128),
    operator: UserRequest = Depends(_require_resource_manager),
    service: Service = Depends(get_auth_service),
) -> Result[ResourceImpactResponse]:
    result = await _run_management(
        service.get_resource_impact,
        resource_type,
        resource_id,
        new_account_set_id,
        operator,
    )
    return Result.succ(result)


@router.patch(
    "/resources/{resource_type}/{resource_id}/account-set",
    response_model=Result[ResourceResponse],
)
async def assign_resource_account(
    resource_type: ResourceTypeName,
    resource_id: str,
    request: AssignResourceAccountRequest,
    operator: UserRequest = Depends(_require_resource_manager),
    service: Service = Depends(get_auth_service),
) -> Result[ResourceResponse]:
    result = await _run_management(
        service.assign_resource_account,
        resource_type,
        resource_id,
        request,
        operator,
    )
    return Result.succ(result)


@router.get("/import/candidates", response_model=Result[list[ImportCandidateResponse]])
async def preview_import_candidates(
    limit: int = Query(default=100, ge=1, le=100),
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[list[ImportCandidateResponse]]:
    result = await _run_management(service.preview_import_candidates, operator, limit)
    return Result.succ(result)


@router.post(
    "/import/batch",
    response_model=Result[ImportBatchResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_import_batch(
    request: ImportBatchRequest,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[ImportBatchResponse]:
    result = await _run_management(service.create_from_import, request, operator)
    return Result.succ(result)


@router.get("/import/batches", response_model=Result[Page[ImportBatchResponse]])
async def list_import_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[Page[ImportBatchResponse]]:
    result = await _run_management(
        service.list_import_batches, page, page_size, operator
    )
    return Result.succ(result)


@router.get("/import/batches/{batch_id}", response_model=Result[ImportBatchResponse])
async def get_import_batch(
    batch_id: str,
    operator: UserRequest = Depends(require_permission("USER_MANAGE")),
    service: Service = Depends(get_auth_service),
) -> Result[ImportBatchResponse]:
    result = await _run_management(service.get_import_batch, batch_id, operator)
    return Result.succ(result)
