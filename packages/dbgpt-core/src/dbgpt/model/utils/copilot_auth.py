"""GitHub OAuth device flow for GitHub Copilot.

Implements the same authorization flow as opencode: request a device code,
the user visits ``github.com/login/device`` and enters the code, and the
backend polls GitHub for the OAuth access token. The token is then used as
the ``api_key`` of the ``proxy/github_copilot`` provider (exchanged for a
short-lived Copilot API token at request time).

The OAuth app client id comes from ``GITHUB_COPILOT_OAUTH_CLIENT_ID``; create
an OAuth App at https://github.com/settings/developers (device flow enabled)
to obtain one.
"""

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_DEVICE_CODE_URL = "https://github.com/login/device/code"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"

_DEVICE_FLOW_SCOPE = "read:user"

_DEFAULT_POLL_INTERVAL = 5.0

_TIMEOUT = 15.0

_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def get_oauth_client_id() -> Optional[str]:
    """Return the configured GitHub OAuth app client id, if any."""
    return os.getenv("GITHUB_COPILOT_OAUTH_CLIENT_ID") or None


async def start_device_flow() -> Tuple[bool, str, dict]:
    """Request a device code from GitHub.

    Returns:
        (ok, message, data): on success data contains ``verification_uri``,
        ``user_code``, ``device_code`` and ``interval`` (seconds, float).
    """
    import httpx

    client_id = get_oauth_client_id()
    if not client_id:
        return (
            False,
            (
                "GitHub Copilot device flow requires an OAuth app client id: "
                "create an OAuth App at https://github.com/settings/developers "
                "(enable device flow) and set GITHUB_COPILOT_OAUTH_CLIENT_ID, "
                "or connect with a GitHub Personal Access Token instead."
            ),
            {},
        )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _DEVICE_CODE_URL,
                headers=_HEADERS,
                json={"client_id": client_id, "scope": _DEVICE_FLOW_SCOPE},
            )
    except Exception as e:
        return False, f"network error: {e}", {}
    if resp.status_code != 200:
        return False, f"github returned HTTP {resp.status_code}", {}
    data = resp.json()
    if not data.get("device_code") or not data.get("user_code"):
        return False, "github returned an invalid device code response", {}
    return (
        True,
        "",
        {
            "verification_uri": data.get("verification_uri")
            or "https://github.com/login/device",
            "user_code": data["user_code"],
            "device_code": data["device_code"],
            "interval": float(data.get("interval") or _DEFAULT_POLL_INTERVAL),
        },
    )


async def poll_device_flow(device_code: str) -> Tuple[str, Optional[str]]:
    """Poll GitHub once for the device flow result.

    Returns:
        (status, github_token): status is one of ``success``, ``pending``,
        ``slow_down``, ``expired`` or ``failed``; token is set on success.
    """
    import httpx

    client_id = get_oauth_client_id()
    if not client_id:
        return "failed", None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _ACCESS_TOKEN_URL,
                headers=_HEADERS,
                json={
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
    except Exception as e:
        logger.warning(f"copilot device flow poll failed: {e}")
        return "failed", None
    if resp.status_code != 200:
        return "failed", None
    data = resp.json()
    token = data.get("access_token")
    if token:
        return "success", token
    error = data.get("error")
    if error == "authorization_pending":
        return "pending", None
    if error == "slow_down":
        return "slow_down", None
    if error == "expired_token":
        return "expired", None
    return "failed", None
