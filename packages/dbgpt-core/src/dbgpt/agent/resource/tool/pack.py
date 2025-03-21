"""Tool resource pack module."""

import os
from typing import Any, Callable, Dict, List, Optional, Type, Union, cast

from mcp import ClientSession
from mcp.client.sse import sse_client

from ..base import ResourceType, T
from ..pack import Resource, ResourcePack
from .base import DB_GPT_TOOL_IDENTIFIER, BaseTool, FunctionTool, ToolFunc
from .exceptions import ToolExecutionException, ToolNotFoundException

ToolResourceType = Union[BaseTool, List[BaseTool], ToolFunc, List[ToolFunc]]


def _is_function_tool(resources: Any) -> bool:
    return (
        callable(resources)
        and hasattr(resources, DB_GPT_TOOL_IDENTIFIER)
        and getattr(resources, DB_GPT_TOOL_IDENTIFIER)
        and hasattr(resources, "_tool")
        and isinstance(getattr(resources, "_tool"), BaseTool)
    )


def _to_tool_list(resources: ToolResourceType) -> List[BaseTool]:
    if isinstance(resources, BaseTool):
        return [resources]
    elif isinstance(resources, list) and all(
        isinstance(r, BaseTool) for r in resources
    ):
        return cast(List[BaseTool], resources)
    elif isinstance(resources, list) and all(_is_function_tool(r) for r in resources):
        return [cast(FunctionTool, getattr(r, "_tool")) for r in resources]
    elif _is_function_tool(resources):
        function_tool = cast(FunctionTool, getattr(resources, "_tool"))
        return [function_tool]
    raise ValueError("Invalid tool resource type")


class ToolPack(ResourcePack):
    """Tool resource pack class."""

    def __init__(
        self, resources: ToolResourceType, name: str = "Tool Resource Pack", **kwargs
    ):
        """Initialize the tool resource pack."""
        tools = cast(List[Resource], _to_tool_list(resources))
        super().__init__(resources=tools, name=name, **kwargs)

    @classmethod
    def from_resource(
        cls: Type[T],
        resource: Optional[Resource],
        expected_type: Optional[ResourceType] = None,
    ) -> List[T]:
        """Create a resource from another resource."""
        if not resource:
            return []
        if isinstance(resource, ToolPack):
            return [cast(T, resource)]
        tools = super().from_resource(resource, ResourceType.Tool)
        if not tools:
            return []
        typed_tools = [cast(BaseTool, t) for t in tools]
        return [ToolPack(typed_tools)]  # type: ignore

    def add_command(
        self,
        command_label: str,
        command_name: str,
        args: Optional[Dict[str, Any]] = None,
        function: Optional[Callable] = None,
    ) -> None:
        """Add a command to the commands.

        Compatible with the Auto-GPT old plugin system.

        Add a command to the commands list with a label, name, and optional arguments.

        Args:
            command_label (str): The label of the command.
            command_name (str): The name of the command.
            args (dict, optional): A dictionary containing argument names and their
              values. Defaults to None.
            function (callable, optional): A callable function to be called when
                the command is executed. Defaults to None.
        """
        if args is not None:
            tool_args = {}
            for name, value in args.items():
                if isinstance(value, dict):
                    tool_args[name] = {
                        "name": name,
                        "type": value.get("type", "str"),
                        "description": value.get("description", str(value)),
                        "required": value.get("required", False),
                    }
                    if "title" in value:
                        tool_args[name]["title"] = value["title"]
                    if "default" in value:
                        tool_args[name]["default"] = value["default"]
                else:
                    tool_args[name] = {
                        "name": name,
                        "type": "str",
                        "description": value,
                    }
        else:
            tool_args = {}
        if not function:
            raise ValueError("Function must be provided")

        ft = FunctionTool(
            name=command_name,
            func=function,
            args=tool_args,
            description=command_label,
        )
        self.append(ft)

    def _get_execution_tool(
        self,
        name: Optional[str] = None,
    ) -> BaseTool:
        if not name and name not in self._resources:
            raise ToolNotFoundException("No tool found for execution")
        return cast(BaseTool, self._resources[name])

    def _get_call_args(self, arguments: Dict[str, Any], tl: BaseTool) -> Dict[str, Any]:
        """Get the call arguments."""
        # Delete non-defined parameters
        diff_args = list(set(arguments.keys()).difference(set(tl.args.keys())))
        for arg_name in diff_args:
            del arguments[arg_name]
        return arguments

    def execute(
        self,
        *args,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute the tool.

        Args:
            *args: The positional arguments.
            resource_name (str, optional): The tool name to be executed.
            **kwargs: The keyword arguments.

        Returns:
            Any: The result of the tool execution.
        """
        tl = self._get_execution_tool(resource_name)
        try:
            arguments = {k: v for k, v in kwargs.items()}
            arguments = self._get_call_args(arguments, tl)
            if tl.is_async:
                raise ToolExecutionException("Async execution is not supported")
            else:
                return tl.execute(**arguments)
        except Exception as e:
            raise ToolExecutionException(f"Execution error: {str(e)}")

    async def async_execute(
        self,
        *args,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute the tool asynchronously.

        Args:
            *args: The positional arguments.
            resource_name (str, optional): The tool name to be executed.
            **kwargs: The keyword arguments.

        Returns:
            Any: The result of the tool execution.
        """
        tl = self._get_execution_tool(resource_name)
        try:
            arguments = {k: v for k, v in kwargs.items()}
            arguments = self._get_call_args(arguments, tl)
            if tl.is_async:
                return await tl.async_execute(**arguments)
            else:
                # TODO: Execute in a separate executor
                return tl.execute(**arguments)
        except Exception as e:
            raise ToolExecutionException(f"Execution error: {str(e)}")


class AutoGPTPluginToolPack(ToolPack):
    """Auto-GPT plugin tool pack class."""

    def __init__(self, plugin_path: Union[str, List[str]], **kwargs):
        """Create an Auto-GPT plugin tool pack."""
        super().__init__([], **kwargs)
        self._plugin_path = plugin_path
        self._loaded = False

    async def preload_resource(self):
        """Preload the resource."""
        from .autogpt.plugins_util import scan_plugin_file, scan_plugins

        if self._loaded:
            return
        paths = (
            [self._plugin_path]
            if isinstance(self._plugin_path, str)
            else self._plugin_path
        )
        plugins = []
        for path in paths:
            if os.path.isabs(path):
                if not os.path.exists(path):
                    raise ValueError(f"Wrong plugin path configured {path}!")
                if os.path.isfile(path):
                    plugins.extend(scan_plugin_file(path))
                else:
                    plugins.extend(scan_plugins(path))
        for plugin in plugins:
            if not plugin.can_handle_post_prompt():
                continue
            plugin.post_prompt(self)
        self._loaded = True


async def call_mcp_tool(server, tool_name, args: dict):
    try:
        async with sse_client(url=server) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                return await session.call_tool(tool_name, arguments=args)
    except Exception:
        raise ValueError("MCP Call Exception!{str(e)}")


class MCPToolPack(ToolPack):
    def __init__(self, mcp_servers: Union[str, List[str]], **kwargs):
        """Create an Auto-GPT plugin tool pack."""
        super().__init__([], **kwargs)
        self._mcp_servers = mcp_servers
        self._loaded = False
        self.tool_server_map = {}

    @classmethod
    def from_resource(
        cls: Type[T],
        resource: Optional[Resource],
        expected_type: Optional[ResourceType] = None,
    ) -> List[T]:
        """Create a resource from another resource."""
        if not resource:
            return []
        if isinstance(resource, ToolPack):
            return [cast(T, resource)]
        tools = super().from_resource(resource, ResourceType.Tool)
        if not tools:
            return []
        typed_tools = [cast(BaseTool, t) for t in tools]
        return [ToolPack(typed_tools)]  # type: ignore

    def _get_call_args(self, arguments: Dict[str, Any], tl: BaseTool) -> Dict[str, Any]:
        """Get the call arguments."""
        # Delete non-defined parameters
        diff_args = list(set(arguments.keys()).difference(set(tl.args.keys())))
        for arg_name in diff_args:
            del arguments[arg_name]

        # Rebuild dbgpt mcp call param
        return {
            "server": self.tool_server_map[tl.name],
            "args": arguments,
            "tool_name": tl.name,
        }

    def switch_mcp_input_schema(self, input_schema: dict):
        args = {}
        try:
            properties = input_schema["properties"]
            required = input_schema["required"]
            for k, v in properties.items():
                arg = {}

                title = v.get("title", None)
                description = v.get("description", None)
                items = v.get("items", None)
                items_str = str(items) if items else None
                any_of = v.get("anyOf", None)
                any_of_str = str(any_of) if any_of else None

                default = v.get("default", None)
                type = v.get("type", "string")

                arg["type"] = type
                if title:
                    arg["title"] = title
                arg["description"] = description or items_str or any_of_str or str(v)
                arg["required"] = True if k in required else False
                if default:
                    arg["default"] = default
                args[k] = arg
            return args
        except Exception as e:
            raise ValueError(f"MCP input_schema can't parase!{str(e)},{input_schema}")

    async def preload_resource(self):
        """Preload the resource."""
        server_list = []
        if isinstance(self._mcp_servers, List):
            server_list = self._mcp_servers.copy()
        else:
            server_list = self._mcp_servers.split(";")

        for server in server_list:
            async with sse_client(url=server) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the connection
                    await session.initialize()
                    result = await session.list_tools()
                    for tool in result.tools:
                        self.tool_server_map[tool.name] = server
                        args = self.switch_mcp_input_schema(tool.inputSchema)
                        self.add_command(
                            tool.description, tool.name, args, call_mcp_tool
                        )
        self._loaded = True
