"""execute_tool tool — run a registered business tool by name."""

import json
from typing import Any, Dict

from dbgpt.agent.resource.tool.base import tool


def make_execute_tool(react_state: Dict[str, Any]):
    @tool(description="Execute a tool by name with JSON args.")
    async def execute_tool(tool_name: str, args: dict) -> str:
        from dbgpt._private.config import Config
        from dbgpt.agent.resource.manage import get_resource_manager
        from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
        from dbgpt.agent.resource.tool.pack import ToolPack

        CFG = Config()
        rm = get_resource_manager(CFG.SYSTEM_APP)
        try:
            tool_resource = rm.build_resource_by_type(
                ResourceType.Tool.value,
                AgentResource(type=ResourceType.Tool.value, value=tool_name),
            )
            tool_pack = ToolPack([tool_resource])
            result = await tool_pack.async_execute(resource_name=tool_name, **args)
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": str(result)}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Tool execute failed: {e}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    return execute_tool
