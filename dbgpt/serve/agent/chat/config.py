from dataclasses import dataclass, field
from typing import Optional

from dbgpt.serve.core import BaseServeConfig

APP_NAME = "agent/chat"
SERVE_APP_NAME = "dbgpt_serve_agent/chat"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Agent/chat"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.agent/chat."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_agent/chat"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    # TODO: add your own parameters here
    api_keys: Optional[str] = field(
        default=None, metadata={"help": "API keys for the endpoint, if None, allow all"}
    )
