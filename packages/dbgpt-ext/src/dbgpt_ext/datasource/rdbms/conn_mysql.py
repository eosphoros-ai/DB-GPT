"""MySQL connector."""

from dataclasses import dataclass, field
from typing import Type

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _


@auto_register_resource(
    label=_("MySQL datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Fast, reliable, scalable open-source relational database management system."
    ),
)
@dataclass
class MySQLParameters(RDBMSDatasourceParameters):
    """MySQL connection parameters."""

    __type__ = "mysql"

    driver: str = field(
        default="mysql+pymysql",
        metadata={
            "help": _("Driver name for MySQL, default is mysql+pymysql."),
        },
    )

    def create_connector(self) -> "MySQLConnector":
        return MySQLConnector.from_parameters(self)


class MySQLConnector(RDBMSConnector):
    """MySQL connector."""

    db_type: str = "mysql"
    db_dialect: str = "mysql"
    driver: str = "mysql+pymysql"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]

    @classmethod
    def param_class(cls) -> Type[RDBMSDatasourceParameters]:
        """Return the parameter class."""
        return MySQLParameters
