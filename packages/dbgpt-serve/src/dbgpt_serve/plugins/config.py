from dataclasses import dataclass, field
from typing import Optional

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "plugins"
SERVE_APP_NAME = "dbgpt_serve_plugins"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Plugins"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.plugins."
SERVE_SERVICE_COMPONENT_NAME = f"{APP_NAME}_service"
# Database table names.  Module naming = plugins (product sidebar module),
# domain object = suite (plugin.json or legacy suite.yaml / assets/suites/).
SERVER_APP_TABLE_NAME = "dbgpt_serve_plugins"
SERVER_EVENT_TABLE_NAME = "dbgpt_serve_plugins_event"
SERVER_HUB_TABLE_NAME = "dbgpt_serve_plugins_hub"


@auto_register_resource(
    label=_("Plugins Serve Configurations"),
    category=ResourceCategory.COMMON,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("This configuration is for the plugins (expert suite) module."),
    show_in_ui=False,
)
@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the plugins serve module."""

    __type__ = APP_NAME

    suites_dir: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Directory holding expert plugins (plugin.json or legacy suite.yaml). "
                "Falls back to $DBGPT_SUITES_DIR, then <cwd>/assets/suites."
            )
        },
    )
