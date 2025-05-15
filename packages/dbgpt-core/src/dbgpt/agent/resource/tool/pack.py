"""Tool resource pack module."""

import logging
import os
import ssl
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union, cast

from mcp import ClientSession

from dbgpt.util.json_utils import parse_or_raise_error

from ...util.mcp_utils import sse_client
from ..base import EXECUTE_ARGS_TYPE, PARSE_EXECUTE_ARGS_FUNCTION, ResourceType, T
from ..pack import Resource, ResourcePack
from .base import DB_GPT_TOOL_IDENTIFIER, BaseTool, FunctionTool, ToolFunc
from .exceptions import ToolExecutionException, ToolNotFoundException

ToolResourceType = Union[Resource, BaseTool, List[BaseTool], ToolFunc, List[ToolFunc]]

logger = logging.getLogger(__name__)


def _is_function_tool(resources: Any) -> bool:
    return (
        callable(resources)
        and hasattr(resources, DB_GPT_TOOL_IDENTIFIER)
        and getattr(resources, DB_GPT_TOOL_IDENTIFIER)
        and hasattr(resources, "_tool")
        and isinstance(getattr(resources, "_tool"), BaseTool)
    )


def _is_tool(resources: Any) -> bool:
    return isinstance(resources, BaseTool) or _is_function_tool(resources)


def _to_tool_list(
    resources: ToolResourceType, unpack: bool = False, ignore_error: bool = False
) -> List[Resource]:
    def parse_tool(r):
        if isinstance(r, BaseTool):
            return [r]
        elif _is_function_tool(r):
            return [cast(FunctionTool, getattr(r, "_tool"))]
        elif isinstance(r, ResourcePack):
            if not unpack:
                return [r]
            new_list = []
            for p in r.sub_resources:
                new_list.extend(parse_tool(p))
            return new_list
        elif isinstance(r, Sequence):
            new_list = []
            for t in r:
                new_list.extend(parse_tool(t))
            return new_list
        elif ignore_error:
            return []
        else:
            raise ValueError("Invalid tool resource type")

    return parse_tool(resources)


def json_parse_execute_args_func(input_str: str) -> Optional[EXECUTE_ARGS_TYPE]:
    """Parse the execute arguments."""
    # The position arguments is empty
    args = ()
    kwargs = parse_or_raise_error(input_str)
    if kwargs is not None and isinstance(kwargs, list) and len(kwargs) == 0:
        kwargs = {}
    return args, kwargs


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
        tools = _to_tool_list(resource, unpack=True, ignore_error=True)
        typed_tools = [cast(BaseTool, t) for t in tools]
        return [ToolPack(typed_tools)]  # type: ignore

    def add_command(
        self,
        command_label: str,
        command_name: str,
        args: Optional[Dict[str, Any]] = None,
        function: Optional[Callable] = None,
        parse_execute_args_func: Optional[PARSE_EXECUTE_ARGS_FUNCTION] = None,
        overwrite: bool = False,
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
            parse_execute_args (callable, optional): A callable function to parse the
                execute arguments. Defaults to None.
            overwrite (bool, optional): Whether to overwrite the command if it already
                exists. Defaults to False.
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
            parse_execute_args_func=parse_execute_args_func,
        )
        self.append(ft, overwrite=overwrite)

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

    def parse_execute_args(
        self, resource_name: Optional[str] = None, input_str: Optional[str] = None
    ) -> Optional[EXECUTE_ARGS_TYPE]:
        """Parse the execute arguments."""
        try:
            tl = self._get_execution_tool(resource_name)
            return tl.parse_execute_args(input_str=input_str)
        except ToolNotFoundException:
            return None

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

    def is_terminal(self, resource_name: Optional[str] = None) -> bool:
        """Check if the tool is terminal."""
        from ...expand.actions.react_action import Terminate

        if not resource_name:
            return False
        tl = self._get_execution_tool(resource_name)
        return isinstance(tl, Terminate)


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


class MCPToolPack(ToolPack):
    """MCP tool pack class.

    Wrap the MCP SSE server as a tool pack.

    Example:
        .. code-block:: python

            tools = MCPToolPack("http://127.0.0.1:8000/sse")

        If you want to pass the token to the server, you can use the headers parameter:
        .. code-block:: python

            tools = MCPToolPack(
                "http://127.0.0.1:8000/sse"
                default_headers={"Authorization": "Bearer your_token"}
            )
            # Set the default headers for ech server
            tools2 = MCPToolPack(
                "http://127.0.0.1:8000/sse"
                headers = {
                    "http://127.0.0.1:8000/sse": {
                        "Authorization": "Bearer your_token"
                    }
                }
            )

        If you want to set the ssl verify, you can use the ssl_verify parameter:
        .. code-block:: python

            # Default ssl_verify is True
            tools = MCPToolPack(
                "https://your_ssl_domain/sse",
            )

            # Set the default ssl_verify to False to disable ssl verify
            tools2 = MCPToolPack(
                "https://your_ssl_domain/sse", default_ssl_verify=False
            )

            # With Custom CA file
            tools3 = MCPToolPack(
                "https://your_ssl_domain/sse", default_ssl_cafile="/path/to/your/ca.crt"
            )

            # Set the ssl_verify for each server
            import ssl

            tools4 = MCPToolPack(
                "https://your_ssl_domain/sse",
                ssl_verify={
                    "https://your_ssl_domain/sse": ssl.create_default_context(
                        cafile="/path/to/your/ca.crt"
                    ),
                },
            )

    """

    def __init__(
        self,
        mcp_servers: Union[str, List[str]],
        headers: Optional[Dict[str, Dict[str, Any]]] = None,
        default_headers: Optional[Dict[str, Any]] = None,
        ssl_verify: Optional[Dict[str, Union[ssl.SSLContext, str, bool]]] = None,
        default_ssl_verify: Union[ssl.SSLContext, str, bool] = True,
        default_ssl_cafile: Optional[str] = None,
        overwrite_same_tool: bool = True,
        **kwargs,
    ):
        """Create an Auto-GPT plugin tool pack."""
        super().__init__([], **kwargs)
        self._mcp_servers = mcp_servers
        self._loaded = False
        self.tool_server_map = {}
        self._default_headers = default_headers or {}
        self._headers_map = headers or {}
        self.server_headers_map = {}
        if default_ssl_cafile and not ssl_verify and default_ssl_verify:
            default_ssl_verify = ssl.create_default_context(cafile=default_ssl_cafile)

        self._default_ssl_verify = default_ssl_verify
        self._ssl_verify_map = ssl_verify or {}
        self.server_ssl_verify_map = {}
        self._overwrite_same_tool = overwrite_same_tool

    def switch_mcp_input_schema(self, input_schema: dict):
        args = {}
        try:
            properties = input_schema["properties"]
            required = input_schema.get("required", [])
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
            server_headers = self._headers_map.get(server, self._default_headers)
            self.server_headers_map[server] = server_headers
            server_ssl_verify = self._ssl_verify_map.get(
                server, self._default_ssl_verify
            )
            self.server_ssl_verify_map[server] = server_ssl_verify

            async with sse_client(
                url=server, headers=server_headers, verify=server_ssl_verify
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the connection
                    await session.initialize()
                    result = await session.list_tools()
                    for tool in result.tools:
                        tool_name = tool.name
                        self.tool_server_map[tool_name] = server
                        args = self.switch_mcp_input_schema(tool.inputSchema)

                        async def call_mcp_tool(
                            tool_name=tool_name, server=server, **kwargs
                        ):
                            try:
                                headers_to_use = self.server_headers_map.get(server, {})
                                ssl_verify_to_use = self.server_ssl_verify_map.get(
                                    server, True
                                )
                                async with sse_client(
                                    url=server,
                                    headers=headers_to_use,
                                    verify=ssl_verify_to_use,
                                ) as (read, write):
                                    async with ClientSession(read, write) as session:
                                        # Initialize the connection
                                        await session.initialize()
                                        return await session.call_tool(
                                            tool_name, arguments=kwargs
                                        )
                            except Exception as e:
                                raise ValueError(f"MCP Call Exception! {str(e)}")

                        self.add_command(
                            tool.description,
                            tool_name,
                            args,
                            call_mcp_tool,
                            parse_execute_args_func=json_parse_execute_args_func,
                            overwrite=self._overwrite_same_tool,
                        )
        self._loaded = True
