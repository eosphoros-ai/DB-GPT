from dataclasses import dataclass, field
from typing import Optional

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "connector"
SERVE_APP_NAME = "dbgpt_serve_connector"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Connector"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.connector."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
SERVER_APP_TABLE_NAME = "connector_instance"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the connector serve command."""

    __type__ = APP_NAME
    SERVE_APP_NAME = APP_NAME
    SERVE_APP_NAME_HUMP = "Connector"

    default_user: Optional[str] = field(
        default=None,
        metadata={"help": "Default user name for connector"},
    )
    default_sys_code: Optional[str] = field(
        default=None,
        metadata={"help": "Default system code for connector"},
    )
