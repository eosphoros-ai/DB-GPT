import logging
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt._private.pydantic import BaseModel

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class UserRequest(BaseModel):
    user_id: Optional[str] = None
    user_no: Optional[str] = None
    real_name: Optional[str] = None
    user_name: Optional[str] = None
    user_channel: Optional[str] = None
    role: Optional[str] = "normal"
    nick_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    nick_name_like: Optional[str] = None
    user_group_id: Optional[int] = None


async def get_user_from_headers(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user_id: Optional[str] = Header(None),
):
    # If Bearer token is present, validate JWT
    if auth and auth.credentials:
        try:
            import jwt

            secret = os.environ.get("DBGPT_JWT_SECRET", "dbgpt_default_jwt_secret")
            payload = jwt.decode(auth.credentials, secret, algorithms=["HS256"])
            return UserRequest(
                user_id=str(payload.get("user_id", "")),
                user_name=payload.get("username"),
                role=payload.get("user_role", "normal"),
                nick_name=payload.get("username"),
                real_name=payload.get("real_name"),
                user_group_id=payload.get("user_group_id"),
            )
        except Exception as e:
            logger.exception(f"JWT authentication failed: {e}")
            raise HTTPException(
                status_code=401, detail=f"Authentication failed: {str(e)}"
            )

    # Fallback: user-id header (backward compat for dev/testing)
    if user_id:
        return UserRequest(
            user_id=user_id,
            role="admin",
            nick_name=user_id,
            real_name=user_id,
        )

    # No authentication provided
    return UserRequest(user_id=None, role="normal")
