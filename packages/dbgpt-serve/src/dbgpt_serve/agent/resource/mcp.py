import dataclasses
import logging
from typing import Any, List, Optional, Type, cast

from dbgpt._private.config import Config
from dbgpt.agent.resource import MCPToolPack, PackResourceParameters, ToolPack
from dbgpt.util import ParameterDescription

CFG = Config()

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MCPPackResourceParameters(PackResourceParameters):
    tool_name: str = dataclasses.field(metadata={"help": "Tool name"})

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


class MCPSSEToolPack(ToolPack):
    def __init__(self, mcp_server: str, **kwargs):
        kwargs.pop("name")
        super().__init__([], name="MCP Tool Pack", **kwargs)
        # Select tool name
        self._mcp_server = mcp_server

    @classmethod
    def type_alias(cls) -> str:
        return "tool(mcp(sse))"

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[MCPPackResourceParameters]:
        logger.info(f"resource_parameters_class:{kwargs}")
        mcp_servers = []
        mcp_servers.append(
            {
                "label": "local_mcp_sse_server",
                "key": "http://127.0.0.1:8000/sse",
                "description": "Local MCP SSE server！",
            }
        )

        @dataclasses.dataclass
        class _DynMCPSSEPackResourceParameters(MCPPackResourceParameters):
            tool_name: str = dataclasses.field(
                metadata={
                    "help": "MCP SSE Server URL(Default Local)",
                    "valid_values": mcp_servers,
                }
            )

        return _DynMCPSSEPackResourceParameters

    async def preload_resource(self):
        """Preload the resource."""
        tool_pack: MCPToolPack = MCPToolPack(self._mcp_server)
        if not tool_pack:
            raise ValueError(f"MPC {self._mcp_server} not found")
        self._resources = tool_pack._resources
