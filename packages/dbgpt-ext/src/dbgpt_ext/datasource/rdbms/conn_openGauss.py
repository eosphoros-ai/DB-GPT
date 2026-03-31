"""openGauss connector."""

from dataclasses import dataclass
from typing import Type

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.util.i18n_utils import _

from .conn_gaussdb import GaussDBConnector, GaussDBParameters


@auto_register_resource(
    label=_("openGauss datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("An open-source relational database with PostgreSQL compatibility."),
)
@dataclass
class openGaussParameters(GaussDBParameters):
    """openGauss connection parameters."""

    __type__ = "openGauss"

    def create_connector(self) -> "openGaussConnector":
        """Create openGauss connector."""
        return openGaussConnector.from_parameters(self)


class openGaussConnector(GaussDBConnector):
    """openGauss connector."""

    db_type = "openGauss"
    db_dialect = "openGauss"

    @classmethod
    def param_class(cls) -> Type[openGaussParameters]:
        """Return the parameter class."""
        return openGaussParameters
