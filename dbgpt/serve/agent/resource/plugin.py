import dataclasses
import logging
from typing import Any, List, Optional, Type, cast

from dbgpt._private.config import Config
from dbgpt.agent.resource.pack import PackResourceParameters
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.component import ComponentType
from dbgpt.serve.agent.hub.controller import ModulePlugin
from dbgpt.util.parameter_utils import ParameterDescription

CFG = Config()

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PluginPackResourceParameters(PackResourceParameters):
    tool_name: str = dataclasses.field(metadata={"help": "Tool name"})

    @classmethod
    def _resource_version(cls) -> str:
        """Return the resource version."""
        return "v1"

    @classmethod
    def to_configurations(
        cls,
        parameters: Type["PluginPackResourceParameters"],
        version: Optional[str] = None,
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
    ) -> "PluginPackResourceParameters":
        """Create a new instance from a dictionary."""
        copied_data = data.copy()
        if "tool_name" not in copied_data and "value" in copied_data:
            copied_data["tool_name"] = copied_data.pop("value")
        return super().from_dict(copied_data, ignore_extra_fields=ignore_extra_fields)


class PluginToolPack(ToolPack):
    def __init__(self, tool_name: str, **kwargs):
        kwargs.pop("name")
        super().__init__([], name="Plugin Tool Pack", **kwargs)
        # Select tool name
        self._tool_name = tool_name

    @classmethod
    def type_alias(cls) -> str:
        return "tool(autogpt_plugins)"

    @classmethod
    def resource_parameters_class(cls) -> Type[PluginPackResourceParameters]:
        agent_module: ModulePlugin = CFG.SYSTEM_APP.get_component(
            ComponentType.PLUGIN_HUB, ModulePlugin
        )
        tool_names = []
        for name, sub_tool in agent_module.tools._resources.items():
            tool_names.append(name)

        @dataclasses.dataclass
        class _DynPluginPackResourceParameters(PluginPackResourceParameters):
            tool_name: str = dataclasses.field(
                metadata={"help": "Tool name", "valid_values": tool_names}
            )

        return _DynPluginPackResourceParameters

    def preload_resource(self):
        """Preload the resource."""
        agent_module: ModulePlugin = CFG.SYSTEM_APP.get_component(
            ComponentType.PLUGIN_HUB, ModulePlugin
        )
        tool = agent_module.tools._resources.get(self._tool_name)
        if not tool:
            raise ValueError(f"Tool {self._tool_name} not found")
        self._resources = {tool.name: tool}
