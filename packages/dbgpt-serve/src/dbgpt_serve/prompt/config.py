from dataclasses import dataclass, field
from typing import Optional

from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

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

    __type__ = APP_NAME

    default_user: Optional[str] = field(
        default=None,
        metadata={"help": _("Default user name for prompt")},
    )
    default_sys_code: Optional[str] = field(
        default=None,
        metadata={"help": _("Default system code for prompt")},
    )
