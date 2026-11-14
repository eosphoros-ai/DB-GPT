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
    if not configured_keys:
        return UserRequest(user_id="001", role="normal")

    if isinstance(configured_keys, str):
        configured_keys = configured_keys.split(",")
    keys = [key.strip() for key in configured_keys if key.strip()]
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


async def v1_auth_middleware(request: Request, call_next):
    """Guard v1 routes that have no identity dependency."""
    path = request.url.path
    if path == "/api/v1" or path.startswith("/api/v1/"):
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
