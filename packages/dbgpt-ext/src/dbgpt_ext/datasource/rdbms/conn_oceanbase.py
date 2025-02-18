"""Ocean base connect."""

import logging
from dataclasses import dataclass, field
from typing import Type

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("OceanBase datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("An Ultra-Fast & Cost-Effective Distributed SQL Database."),
)
@dataclass
class OceanBaseParameters(RDBMSDatasourceParameters):
    """Oceanbase connection parameters."""

    __type__ = "oceanbase"
    driver: str = field(
        default="mysql+ob",
        metadata={
            "help": _("Driver name for oceanbase, default is mysql+ob."),
        },
    )

    def create_connector(self) -> "OceanBaseConnector":
        return OceanBaseConnector.from_parameters(self)


class OceanBaseConnector(RDBMSConnector):
    """Connect Oceanbase Database fetch MetaData.

    Args:
    Usage:
    """

    db_type: str = "oceanbase"
    db_dialect: str = "mysql"
    driver: str = "mysql+ob"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]

    @classmethod
    def param_class(cls) -> Type[OceanBaseParameters]:
        """Return the parameter class."""
        return OceanBaseParameters

    def get_users(self):
        """Get_users."""
        return []

    def get_grants(self):
        """Get_grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get_charset."""
        return "UTF-8"
