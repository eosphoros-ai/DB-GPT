import dataclasses
import logging
from typing import Any, List, Optional, Type, Union, cast

from dbgpt.agent.resource import MCPToolPack, PackResourceParameters
from dbgpt.util import ParameterDescription
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MCPPackResourceParameters(PackResourceParameters):
    @classmethod
    def _resource_version(cls) -> str:
        """Return the resource version."""
        return "v1"

    @classmethod
    def to_configurations(
        cls,
        parameters: Type["MCPPackResourceParameters"],
        version: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Convert the parameters to configurations."""
        conf: List[ParameterDescription] = cast(
            List[ParameterDescription], super().to_configurations(parameters)
        )
        version = version or cls._resource_version()
        if version != "v1":
            return conf
        # Compatible with old version
        for param in conf:
            if param.param_name == "tool_name":
                return param.valid_values or []
        return []

    @classmethod
    def from_dict(
        cls, data: dict, ignore_extra_fields: bool = True
    ) -> "MCPPackResourceParameters":
        """Create a new instance from a dictionary."""
        copied_data = data.copy()
        if "mcp_server" not in copied_data and "value" in copied_data:
            copied_data["mcp_server"] = copied_data.pop("value")
        return super().from_dict(copied_data, ignore_extra_fields=ignore_extra_fields)


class MCPSSEToolPack(MCPToolPack):
    def __init__(self, mcp_servers: Union[str, List[str]], **kwargs):
        super().__init__(mcp_servers=mcp_servers, **kwargs)

    @classmethod
    def type_alias(cls) -> str:
        return "tool(mcp(sse))"

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[MCPPackResourceParameters]:
        logger.info(f"resource_parameters_class:{kwargs}")

        @dataclasses.dataclass
        class _DynMCPSSEPackResourceParameters(MCPPackResourceParameters):
            mcp_servers: str = dataclasses.field(
                default="http://127.0.0.1:8000/sse",
                metadata={
                    "help": _("MCP SSE Server URL, split by ':'"),
                },
            )

        return _DynMCPSSEPackResourceParameters
