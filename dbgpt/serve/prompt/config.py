from dataclasses import dataclass

from dbgpt.serve.core import BaseServeConfig


APP_NAME = "prompt"
SERVE_APP_NAME = "dbgpt_serve_prompt"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Prompt"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.prompt."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_prompt"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    # TODO: add your own parameters here
