"""Authentication dependencies shared by DB-GPT HTTP endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt_serve.auth.constants import ROLE_PERMISSIONS
from dbgpt_serve.auth.service.service import (
    AuthConfigurationError,
    AuthenticationError,
    Service,
    get_auth_service,
)

_bearer_scheme = HTTPBearer(auto_error=False)


class UserRequest(BaseModel):
    """Current user plus legacy aliases used by existing endpoints."""

    user_id: Optional[str] = None
    login_name: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = "normal"
    is_active: bool = True
    session_id: Optional[str] = Field(default=None, exclude=True)
    gmt_created: Optional[datetime] = None
    disabled_at: Optional[datetime] = None

    # Compatibility fields for existing endpoint and unit-test call sites.
    user_no: Optional[str] = None
    real_name: Optional[str] = None
    user_name: Optional[str] = None
    user_channel: Optional[str] = None
    nick_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    nick_name_like: Optional[str] = None


def _not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    service: Service = Depends(get_auth_service),
) -> UserRequest:
    """Authenticate from a bearer token or the secure session cookie."""
    token = auth.credentials if auth and auth.scheme.lower() == "bearer" else None
    if not token:
        token = request.cookies.get("dbgpt_session")
    if not token:
        raise _not_authenticated()

    try:
        user, session_id = service.authenticate_token(token)
    except AuthenticationError as exc:
        raise _not_authenticated() from exc
    except AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc

    return UserRequest(
        user_id=user.user_id,
        login_name=user.login_name,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        session_id=session_id,
        gmt_created=user.gmt_created,
        disabled_at=user.disabled_at,
        user_no=user.user_id,
        real_name=user.display_name,
        user_name=user.login_name,
        nick_name=user.display_name,
    )


async def get_user_from_headers(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    service: Service = Depends(get_auth_service),
) -> UserRequest:
    """Compatibility name for endpoints that previously used mock header auth."""
    return await get_current_user(request, auth, service)


def require_permission(permission: str):
    """Build a FastAPI dependency that enforces a fixed role permission."""

    async def dependency(
        user: UserRequest = Depends(get_current_user),
    ) -> UserRequest:
        if permission not in ROLE_PERMISSIONS.get(user.role or "", set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return user

    return dependency


def require_admin():
    """Require the system-administrator user-management capability."""
    return require_permission("USER_MANAGE")
