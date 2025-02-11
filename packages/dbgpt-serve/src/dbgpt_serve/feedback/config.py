from dataclasses import dataclass

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "feedback"
SERVE_APP_NAME = "dbgpt_serve_feedback"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Feedback"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.feedback."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_feedback"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME
