"""Authentication dependencies shared by DB-GPT HTTP endpoints."""

import uuid
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
_SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class UserRequest(BaseModel):
    """Current user plus legacy aliases used by existing endpoints."""

    user_id: Optional[str] = None
    login_name: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = "normal"
    is_active: bool = True
    session_id: Optional[str] = Field(default=None, exclude=True)
    source_ip: Optional[str] = Field(default=None, exclude=True)
    user_agent: Optional[str] = Field(default=None, exclude=True)
    request_id: Optional[str] = Field(default=None, exclude=True)
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
    bearer_token = (
        auth.credentials if auth and auth.scheme.lower() == "bearer" else None
    )
    token = bearer_token
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

    if request.method.upper() not in _SAFE_HTTP_METHODS and not bearer_token:
        csrf_cookie = request.cookies.get("dbgpt_csrf", "")
        csrf_header = request.headers.get("x-csrf-token", "")
        if csrf_cookie != csrf_header or not service.validate_csrf_token(
            token, csrf_header
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed",
            )

    raw_request_id = getattr(request.state, "request_id", None)
    request_id = str(raw_request_id).strip()[:128] if raw_request_id else ""

    return UserRequest(
        user_id=user.user_id,
        login_name=user.login_name,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        session_id=session_id,
        source_ip=(request.client.host if request.client else "")[:64] or None,
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=request_id or str(uuid.uuid4()),
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
