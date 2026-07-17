"""Authentication endpoints for the administration API."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from starlette.concurrency import run_in_threadpool

from dbgpt.core.schema.api import Result
from dbgpt_serve.auth.api.schemas import LoginRequest, LoginResponse, UserResponse
from dbgpt_serve.auth.service.service import (
    AuthConfigurationError,
    AuthenticationError,
    Service,
    get_auth_service,
)
from dbgpt_serve.utils.auth import UserRequest, get_current_user

router = APIRouter()


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
