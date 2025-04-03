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
        """Initialize the MCPSSEToolPack with the given MCP servers."""
        headers = {}
        if "token" in kwargs and kwargs["token"]:
            # token is not supported in sse mode
            servers = (
                mcp_servers.split(";") if isinstance(mcp_servers, str) else mcp_servers
            )
            tokens = (
                kwargs["token"].split(";")
                if isinstance(kwargs["token"], str)
                else kwargs["token"]
            )
            if len(servers) == len(tokens):
                for i, token in enumerate(tokens):
                    headers[servers[i]] = {"Authorization": f"Bearer {token}"}
            else:
                token = tokens[0]
                for server in servers:
                    headers[server] = {"Authorization": f"Bearer {token}"}
            kwargs.pop("token")
        super().__init__(mcp_servers=mcp_servers, headers=headers, **kwargs)

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
                    "help": _("MCP SSE Server URL, split by ';'"),
                },
            )
            token: Optional[str] = dataclasses.field(
                default=None,
                metadata={
                    "help": _(
                        'MCP SSE Server token, split by ";", It will be '
                        'added to the header({"Authorization": "Bearer your_token"}'
                    ),
                    "tags": "privacy",
                },
            )

        return _DynMCPSSEPackResourceParameters
