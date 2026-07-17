"""Configuration for the authorization service."""

from dataclasses import dataclass, field

from dbgpt_serve.core.config import BaseServeConfig

APP_NAME = "auth"
SERVE_APP_NAME = "dbgpt_auth"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.auth."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"


@dataclass
class ServeConfig(BaseServeConfig):
    """Authorization service configuration."""

    __type__ = APP_NAME

    jwt_secret: str = field(default="", repr=False, metadata={"tags": "privacy"})
    jwt_access_expire_minutes: int = field(default=480)
    jwt_absolute_expire_minutes: int = field(default=1440)
    login_fail_lock_threshold: int = field(default=5)
    login_fail_lock_minutes: int = field(default=30)
    lszyzd_datasource: str = field(default="LSZYZD")
    lszyzd_table: str = field(default="LSZYZD")
    initial_admin_login: str = field(default="admin")
    initial_admin_password: str = field(
        default="", repr=False, metadata={"tags": "privacy"}
    )
    cookie_secure: bool = field(default=True)
