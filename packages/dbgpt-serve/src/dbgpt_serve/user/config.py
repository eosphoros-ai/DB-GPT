from dataclasses import dataclass, field
from typing import Optional

from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "user"
SERVE_APP_NAME = "dbgpt_serve_user"
SERVE_APP_NAME_HUMP = "dbgpt_serve_User"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.user."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"

SERVER_APP_TABLE_USERS = "users"
SERVER_APP_TABLE_USER_GROUPS = "user_groups"
SERVER_APP_TABLE_USER_GROUP_MENUS = "user_group_menus"

# All available menu keys
ALL_MENU_KEYS = [
    "explore",
    "skills",
    "datasources",
    "knowledge",
    "app_management",
    "model_manage",
    "awel_workflow",
    "prompts",
    "models_evaluation",
    "user_management",
]


@dataclass
class ServeConfig(BaseServeConfig):
    __type__ = APP_NAME

    jwt_secret_key: Optional[str] = field(
        default=None,
        metadata={"help": _("JWT secret key for token signing")},
    )
    jwt_algorithm: str = field(
        default="HS256",
        metadata={"help": _("JWT algorithm")},
    )
    jwt_expire_minutes: int = field(
        default=1440,
        metadata={"help": _("JWT expiration time in minutes")},
    )
