from dataclasses import dataclass

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "dbgpts_my"
SERVE_APP_NAME = "dbgpt_serve_dbgpts_my"
SERVE_APP_NAME_HUMP = "dbgpt_serve_DbgptsMy"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.dbgpts_my."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = SERVE_APP_NAME


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME
