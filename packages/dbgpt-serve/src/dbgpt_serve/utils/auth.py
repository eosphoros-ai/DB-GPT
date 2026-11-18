import hashlib
import hmac
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt._private.pydantic import BaseModel

get_bearer_token = HTTPBearer(auto_error=False)


class UserRequest(BaseModel):
    user_id: Optional[str] = None
    user_no: Optional[str] = None
    real_name: Optional[str] = None
    # same with user_id
    user_name: Optional[str] = None
    user_channel: Optional[str] = None
    role: Optional[str] = "normal"
    nick_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    nick_name_like: Optional[str] = None


def _resolve_user(
    request: Request, auth: Optional[HTTPAuthorizationCredentials]
) -> UserRequest:
    configured_keys = getattr(request.app.state, "api_keys", None)
    path = request.url.path
    for pattern, methods, keys in getattr(request.app.state, "api_keys_by_route", ()):
        if request.method in methods and pattern.fullmatch(path):
            configured_keys = keys
            break
    if not configured_keys and not getattr(
        request.app.state, "v1_api_keys_configured", False
    ):
        return UserRequest(
            user_id="001", role="normal", real_name="dbgpt", nick_name="dbgpt"
        )

    if isinstance(configured_keys, str):
        configured_keys = configured_keys.split(",")
    keys = [key.strip() for key in (configured_keys or ()) if key.strip()]
    token = auth.credentials if auth else None
    if not token or not any(hmac.compare_digest(token, key) for key in keys):
        raise HTTPException(
            status_code=401,
            detail="A valid API key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    owner = "key-" + hashlib.sha256(token.encode("utf-8")).hexdigest()
    return UserRequest(user_id=owner, role="normal", nick_name=owner)


def get_user_from_headers(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
) -> UserRequest:
    """Resolve the caller from a configured API key, never an identity header."""
    return getattr(request.state, "v1_user", None) or _resolve_user(request, auth)


def get_v1_owner(request: Request) -> Optional[str]:
    """Return the middleware-verified owner without changing v2 serve contracts."""
    path = request.url.path
    if path != "/api/v1" and not path.startswith("/api/v1/"):
        return None
    user = getattr(request.state, "v1_user", None)
    if user is None or not user.user_id:
        raise HTTPException(status_code=401, detail="A verified owner is required.")
    return user.user_id


def _is_public_v1_route(request: Request) -> bool:
    path = request.url.path
    parts = path.strip("/").split("/")
    if request.method == "GET" and len(parts) == 5:
        return parts[:4] in (
            ["api", "v1", "chat", "share"],
            ["api", "v1", "public", "dashboards"],
        )
    return (
        request.method == "POST"
        and len(parts) == 6
        and parts[:4] == ["api", "v1", "public", "dashboards"]
        and parts[5] == "filter"
    )


async def v1_auth_middleware(request: Request, call_next):
    """Guard v1 routes that have no identity dependency."""
    path = request.url.path
    if (path == "/api/v1" or path.startswith("/api/v1/")) and not _is_public_v1_route(
        request
    ):
        try:
            auth = await get_bearer_token(request)
            request.state.v1_user = _resolve_user(request, auth)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
    return await call_next(request)
