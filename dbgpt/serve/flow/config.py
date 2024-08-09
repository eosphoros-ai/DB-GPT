from dataclasses import dataclass, field
from typing import Optional

from dbgpt.serve.core import BaseServeConfig

APP_NAME = "flow"
SERVE_APP_NAME = "dbgpt_serve_flow"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Flow"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.flow."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
SERVE_VARIABLES_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_variables_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_flow"
SERVER_APP_VARIABLES_TABLE_NAME = "dbgpt_serve_variables"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    # TODO: add your own parameters here
    api_keys: Optional[str] = field(
        default=None, metadata={"help": "API keys for the endpoint, if None, allow all"}
    )
    load_dbgpts_interval: int = field(
        default=5, metadata={"help": "Interval to load dbgpts from installed packages"}
    )
    encrypt_key: Optional[str] = field(
        default=None, metadata={"help": "The key to encrypt the data"}
    )
