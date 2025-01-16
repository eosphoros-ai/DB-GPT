from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from dbgpt.util.parameter_utils import BaseParameters

if TYPE_CHECKING:
    from dbgpt.datasource.base import BaseConnector


@dataclass
class BaseDatasourceParameters(BaseParameters):
    """Base class for datasource parameters."""

    def engine_args(self) -> Optional[Dict[str, Any]]:
        """Return engine arguments."""
        return None

    def create_connector(self) -> "BaseConnector":
        """Create a connector."""
        raise NotImplementedError("Current connector does not support create_connector")
