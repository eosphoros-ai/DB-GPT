from dataclasses import dataclass

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "rag"
SERVE_APP_NAME = "dbgpt_rag"
SERVE_APP_NAME_HUMP = "dbgpt_rag"
SERVE_CONFIG_KEY_PREFIX = "dbgpt_rag"
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME
