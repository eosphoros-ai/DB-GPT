from dataclasses import dataclass, field
from typing import Optional

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "scheduled_task"
SERVE_APP_NAME = "dbgpt_serve_scheduled_task"
SERVE_APP_NAME_HUMP = "dbgpt_serve_ScheduledTask"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.scheduled_task."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
SERVER_APP_TABLE_NAME = "dbgpt_serve_scheduled_task"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the scheduled task serve command."""

    __type__ = APP_NAME
    SERVE_APP_NAME = APP_NAME
    SERVE_APP_NAME_HUMP = "ScheduledTask"

    default_user: Optional[str] = field(
        default=None,
        metadata={"help": "Default user name for scheduled task"},
    )
    default_sys_code: Optional[str] = field(
        default=None,
        metadata={"help": "Default system code for scheduled task"},
    )
