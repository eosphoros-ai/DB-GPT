from dataclasses import dataclass, field
from typing import Optional

from dbgpt.serve.core import BaseServeConfig

APP_NAME = "dbgpts_hub"
SERVE_APP_NAME = "dbgpt_serve_dbgpts_hub"
SERVE_APP_NAME_HUMP = "dbgpt_serve_DbgptsHub"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.dbgpts_hub."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = SERVE_APP_NAME


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    # TODO: add your own parameters here
    api_keys: Optional[str] = field(
        default=None, metadata={"help": "API keys for the endpoint, if None, allow all"}
    )
