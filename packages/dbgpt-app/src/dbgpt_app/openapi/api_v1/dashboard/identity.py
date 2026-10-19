"""Dashboard identity boundary built on top of DB-GPT request identities."""

import importlib
import os
from typing import Optional, Protocol

from dbgpt_serve.utils.auth import UserRequest


class DashboardIdentityError(PermissionError):
    pass


class DashboardIdentityProvider(Protocol):
    """Resolve a trusted, stable actor id for Dashboard authorization."""

    def resolve(self, user: UserRequest) -> str: ...


def dashboard_production_mode() -> bool:
    return os.getenv("DBGPT_DASHBOARD_PRODUCTION_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class DBGPTUserIdentityProvider:
    """Use the upstream DB-GPT identity while rejecting its mock fallback.

    DB-GPT currently returns a recognizable ``001/dbgpt`` user when no identity
    header is supplied.  It remains convenient for local demos, but production
    mode must never treat that mock user as an administrator.
    """

    def __init__(self, *, allow_development_fallback: bool = True) -> None:
        self.allow_development_fallback = allow_development_fallback

    @staticmethod
    def _is_development_fallback(user: UserRequest) -> bool:
        return (
            user.user_id == "001"
            and user.nick_name == "dbgpt"
            and user.real_name == "dbgpt"
        )

    def resolve(self, user: UserRequest) -> str:
        actor_id = user.user_id or user.user_name
        if not actor_id:
            raise DashboardIdentityError(
                "DB-GPT did not provide an authenticated dashboard identity."
            )
        if self._is_development_fallback(user) and not self.allow_development_fallback:
            raise DashboardIdentityError(
                "The DB-GPT development identity is disabled for Dashboard "
                "production mode."
            )
        return actor_id


def _load_provider(path: str) -> DashboardIdentityProvider:
    module_name, separator, attribute = path.rpartition(".")
    if not separator:
        raise RuntimeError(
            "DBGPT_DASHBOARD_IDENTITY_PROVIDER must be a dotted import path."
        )
    provider_type = getattr(importlib.import_module(module_name), attribute)
    provider = provider_type() if isinstance(provider_type, type) else provider_type
    if not callable(getattr(provider, "resolve", None)):
        raise RuntimeError("Dashboard identity provider must define resolve(user).")
    return provider


_identity_provider: Optional[DashboardIdentityProvider] = None


def configure_dashboard_identity_provider(
    provider: Optional[DashboardIdentityProvider],
) -> None:
    """Install a platform adapter during application composition or tests."""

    global _identity_provider
    _identity_provider = provider


def get_dashboard_identity_provider() -> DashboardIdentityProvider:
    global _identity_provider
    if _identity_provider is not None:
        return _identity_provider
    configured_path = os.getenv("DBGPT_DASHBOARD_IDENTITY_PROVIDER", "").strip()
    if configured_path:
        _identity_provider = _load_provider(configured_path)
    else:
        _identity_provider = DBGPTUserIdentityProvider(
            allow_development_fallback=not dashboard_production_mode()
        )
    return _identity_provider
