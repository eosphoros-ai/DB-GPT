from dataclasses import dataclass, field
from typing import Optional

from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "conversation"
SERVE_APP_NAME = "dbgpt_serve_conversation"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Conversation"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.conversation."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_conversation"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME

    default_model: Optional[str] = field(
        default=None,
        metadata={"help": _("Default model for the conversation")},
    )
