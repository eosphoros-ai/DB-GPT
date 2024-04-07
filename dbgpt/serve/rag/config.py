from dataclasses import dataclass, field
from typing import Optional

from dbgpt.serve.core import BaseServeConfig

APP_NAME = "rag"
SERVE_APP_NAME = "dbgpt_rag"
SERVE_APP_NAME_HUMP = "dbgpt_rag"
SERVE_CONFIG_KEY_PREFIX = "dbgpt_rag"
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    api_keys: Optional[str] = field(
        default=None, metadata={"help": "API keys for the endpoint, if None, allow all"}
    )

    default_user: Optional[str] = field(
        default=None,
        metadata={"help": "Default user name for prompt"},
    )
    default_sys_code: Optional[str] = field(
        default=None,
        metadata={"help": "Default system code for prompt"},
    )
