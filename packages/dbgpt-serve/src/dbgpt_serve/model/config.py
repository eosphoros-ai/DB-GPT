from dataclasses import dataclass, field
from typing import Optional

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "model"
SERVE_APP_NAME = "dbgpt_serve_model"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Model"
SERVE_CONFIG_KEY_PREFIX = "dbgpt_serve.model."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_model"


@auto_register_resource(
    label=_("Model Serve Configurations"),
    category=ResourceCategory.COMMON,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("This configuration is for the model serve module."),
    show_in_ui=False,
)
@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME

    model_storage: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The storage type of model configures, if None, use the default "
                "storage(current database). When you run in light mode, it will not "
                "use any storage."
            ),
            "valid_values": ["database", "memory"],
        },
    )
