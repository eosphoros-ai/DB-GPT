"""Host measurements for an explicitly selected operations suite."""

import json

from dbgpt.agent.resource.tool.base import tool


def make_system_health():
    @tool(
        description="Read DB-GPT server host health, not database instance "
        "health. fields selects cpu, memory and/or load."
    )
    def system_health(fields: list[str] | None = None) -> str:
        from dbgpt.agent.expand.resources.host_tool import (
            get_current_host_cpu_status,
            get_current_host_memory_status,
            get_current_host_system_load,
        )

        readers = {
            "cpu": get_current_host_cpu_status,
            "memory": get_current_host_memory_status,
            "load": get_current_host_system_load,
        }
        selected = fields if fields is not None else list(readers)
        if not selected or set(selected) - readers.keys():
            raise ValueError("fields must select cpu, memory and/or load")
        return json.dumps(
            {
                "target": "dbgpt_server_host",
                "metrics": {field: readers[field]() for field in selected},
            },
            ensure_ascii=False,
        )

    return system_health
