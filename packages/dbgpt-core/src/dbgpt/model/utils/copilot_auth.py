"""GitHub OAuth device flow used by the model-provider connection dialog.

The client ID belongs to the deployment's own OAuth App, with Device Flow
enabled. No client secret or third-party application's identity is needed.
"""

import os
from typing import Any, Dict, Optional, Tuple

import httpx

_DEVICE_CODE_URL = "https://github.com/login/device/code"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_VERIFICATION_URI = "https://github.com/login/device"
_HEADERS = {"Accept": "application/json", "User-Agent": "DB-GPT"}
_TIMEOUT = 15.0


def _client_id() -> str:
    return os.getenv("GITHUB_COPILOT_OAUTH_CLIENT_ID", "").strip()


async def start_device_flow() -> Tuple[bool, str, Dict[str, Any]]:
    """Request the codes displayed to the user by the connection dialog."""
    client_id = _client_id()
    if not client_id:
        return False, "GITHUB_COPILOT_OAUTH_CLIENT_ID is not configured", {}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _DEVICE_CODE_URL, data={"client_id": client_id}, headers=_HEADERS
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return False, "GitHub device authorization request failed", {}
    if not isinstance(data, dict):
        return False, "Invalid GitHub device authorization response", {}
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 900)
    if (
        data.get("error")
        or not isinstance(data.get("device_code"), str)
        or not data["device_code"]
        or not isinstance(data.get("user_code"), str)
        or not data["user_code"]
        or data.get("verification_uri") != _VERIFICATION_URI
        or type(interval) is not int
        or interval <= 0
        or type(expires_in) is not int
        or expires_in <= 0
    ):
        return False, "Invalid GitHub device authorization response", {}
    return (
        True,
        "",
        {
            "device_code": data["device_code"],
            "user_code": data["user_code"],
            "verification_uri": _VERIFICATION_URI,
            "interval": interval,
            "expires_in": expires_in,
        },
    )


async def poll_device_flow(device_code: str) -> Tuple[str, Optional[str]]:
    """Poll once; keep the OAuth token on the server for provider setup."""
    client_id = _client_id()
    if not client_id or not device_code:
        return "error", None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _ACCESS_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers=_HEADERS,
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return "error", None
    if not isinstance(data, dict):
        return "error", None
    error = data.get("error")
    if error == "authorization_pending":
        return "pending", None
    if error == "slow_down":
        return "slow_down", None
    token = data.get("access_token")
    if (
        error
        or not isinstance(token, str)
        or not token
        or str(data.get("token_type", "")).lower() != "bearer"
    ):
        return "error", None
    return "success", token
