"""Turn-scoped discovery; never build arbitrary resources from model input."""

import json
import re
from typing import Any, Callable

from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack

RETIRED_ENTRIES = {
    "load_tools",
    "execute_tool",
    "execute_analysis",
    "execute_skill_script",
    "execute_skill_script_file",
    "baidu_search",
    "serply_search",
    "list_dbgpt_support_models",
    "get_current_host_cpu_status",
    "get_current_host_memory_status",
    "get_current_host_system_load",
}
BASE_TOOLS = {"question", "terminate", "read_file", "load_skill", "todowrite"}


def consolidate_tools(resources: list[Any]) -> list[Any]:
    """Remove retired model entries, retaining backend implementations."""
    return [
        resource
        for resource in ToolPack(resources).sub_resources
        if resource.name not in RETIRED_ENTRIES
    ]


def make_scoped_tool_pack(
    resources: list[Any],
    *,
    eager_names: set[str],
    allowed: Callable[[str], bool] | None = None,
    emit: Callable | None = None,
) -> ToolPack:
    """Build an isolated catalog from resources already selected by the caller.

    This helper never resolves new resources. Keep explicit node tools eager;
    use discovery for auxiliary skills, KB readers and connector capabilities.
    """
    candidates = consolidate_tools(resources)
    names = {resource.name for resource in candidates}
    permitted = allowed or (lambda name: name in names)
    pack = ToolPack(
        [
            item
            for item in candidates
            if item.name in eager_names and permitted(item.name)
        ]
    )

    async def notify(event: str, payload: dict) -> None:
        if emit is not None:
            await emit(event, payload)

    pack.append(make_tool_search(candidates, lambda: pack, permitted, notify)._tool)
    return pack


def make_tool_search(
    candidates: list[Any],
    target: Callable[[], ToolPack],
    allowed: Callable[[str], bool],
    emit: Callable,
):
    """Expose only authorized candidates and append them at a round boundary."""
    catalog = {resource.name: resource for resource in candidates}

    @tool(
        description="Find and activate available tools for the current task. "
        "Search by exact tool name or capability keywords. Only tools allowed "
        "in this turn can be discovered. Activated functions become callable "
        "on the next round; discovery never grants extra permissions."
    )
    async def tool_search(query: str, max_results: int = 4) -> str:
        words = set(re.findall(r"[\w]+", query.casefold()))
        matches = []
        for name, resource in catalog.items():
            if not allowed(name):
                continue
            text = (name + " " + resource.description).casefold()
            score = (
                100
                if name.casefold() == query.strip().casefold()
                else sum(word in text for word in words)
            )
            if score:
                matches.append((score, name, resource))
        matches.sort(key=lambda item: (-item[0], item[1]))
        results = []
        pack = target()
        for _, name, resource in matches[: max(1, min(max_results, 8))]:
            if name not in pack._resources:
                pack.append(resource)
            results.append(
                {
                    "name": name,
                    "description": resource.description,
                    "parameters": resource.parameters_schema(),
                }
            )
        if results:
            await emit(
                "tools.activated",
                {
                    "tools": [result["name"] for result in results],
                    "source": "turn_catalog",
                },
            )
        return json.dumps(
            {"tools": results, "available_next_round": True}, ensure_ascii=False
        )

    return tool_search
