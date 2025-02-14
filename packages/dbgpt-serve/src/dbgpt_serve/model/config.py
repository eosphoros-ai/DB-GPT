from dataclasses import dataclass

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "model"
SERVE_APP_NAME = "dbgpt_serve_model"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Model"
SERVE_CONFIG_KEY_PREFIX = "dbgpt_serve.model."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_model"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME

    # TODO: add your own parameters here
