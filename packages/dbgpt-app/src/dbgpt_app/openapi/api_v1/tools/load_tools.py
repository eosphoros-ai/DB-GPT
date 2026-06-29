"""load_tools tool — resolves required tools for the selected skill."""

import json
from typing import Any, Dict

from dbgpt.agent.resource.tool.base import tool


def make_load_tools(react_state: Dict[str, Any]):
    @tool(description="Resolve required tools for the selected skill.")
    def load_tools() -> str:
        from dbgpt._private.config import Config
        from dbgpt.agent.resource.manage import get_resource_manager
        from dbgpt.agent.resource.resource_api import AgentResource, ResourceType

        CFG = Config()
        matched = react_state.get("matched")
        rm = get_resource_manager(CFG.SYSTEM_APP)
        required_tools = matched.metadata.required_tools if matched else []
        if not required_tools:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No required tools specified",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        loaded = []
        failed = []
        for tool_name in required_tools:
            try:
                rm.build_resource_by_type(
                    ResourceType.Tool.value,
                    AgentResource(type=ResourceType.Tool.value, value=tool_name),
                )
                loaded.append(tool_name)
            except Exception as e:
                failed.append(f"{tool_name} ({e})")
        chunks = []
        if loaded:
            chunks.append(
                {"output_type": "text", "content": f"Loaded: {', '.join(loaded)}"}
            )
        if failed:
            chunks.append(
                {"output_type": "text", "content": f"Failed: {', '.join(failed)}"}
            )
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return load_tools
