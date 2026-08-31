import logging
from typing import Optional

from fastapi import Header, HTTPException

from dbgpt._private.pydantic import BaseModel

logger = logging.getLogger(__name__)


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


def _parse_api_keys(api_keys) -> list[str]:
    if not api_keys:
        return []
    if isinstance(api_keys, str):
        return [key.strip() for key in api_keys.split(",") if key.strip()]
    if isinstance(api_keys, (list, tuple, set)):
        return [str(key).strip() for key in api_keys if str(key).strip()]
    return []


def _get_configured_api_keys() -> list[str]:
    try:
        from dbgpt._private.config import Config

        system_app = Config().SYSTEM_APP
        if not system_app or not getattr(system_app, "config", None):
            return []
        return _parse_api_keys(system_app.config.get("dbgpt.app.global.api_keys"))
    except Exception:
        logger.debug("Failed to load configured API keys", exc_info=True)
        return []


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _raise_invalid_api_key() -> None:
    raise HTTPException(
        status_code=401,
        detail={
            "error": {
                "message": "",
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key",
            }
        },
    )


def get_user_from_headers(
    user_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    try:
        api_keys = _get_configured_api_keys()
        if api_keys:
            token = _extract_bearer_token(authorization)
            if token not in api_keys:
                _raise_invalid_api_key()

        # Compatibility user info. Real deployments should map authenticated
        # tokens to stable user identities instead of trusting plain headers.
        if user_id:
            return UserRequest(
                user_id=user_id, role="admin", nick_name=user_id, real_name=user_id
            )
        else:
            return UserRequest(
                user_id="001", role="admin", nick_name="dbgpt", real_name="dbgpt"
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Authentication failed!")
        raise Exception(f"Authentication failed. {str(e)}")
