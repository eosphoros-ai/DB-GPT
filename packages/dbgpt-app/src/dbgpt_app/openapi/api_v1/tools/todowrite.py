"""todowrite tool — maintain a session-level structured task list."""

import json
from typing import Callable, Dict, List

from dbgpt.agent.resource.tool.base import tool


def make_todowrite(
    todo_list: List[Dict[str, str]],
    stream_callback: Callable,
):
    """Return a ``todowrite`` FunctionTool that mutates ``todo_list`` in-place."""

    @tool(
        description=(
            "Create and manage a structured task list for the current session. "
            "Use this tool to plan complex tasks (3+ steps), track progress, "
            "and show the user what you are doing. "
            "Pass the FULL todo list every time (not incremental). "
            "Each todo has: content (brief description), "
            "status (pending | in_progress | completed | cancelled), "
            "priority (high | medium | low). "
            "Rules: only ONE task in_progress at a time; mark tasks completed "
            "immediately after finishing; do NOT use for single trivial tasks."
            '\nParameter: {"todos": [{"content": "...", "status": "...", '
            '"priority": "..."}]}'
        )
    )
    def todowrite(todos: str) -> str:
        """Update the session todo list (full replacement)."""
        parsed: List[Dict[str, str]] = []
        try:
            raw = json.loads(todos) if isinstance(todos, str) else todos
            items = raw if isinstance(raw, list) else raw.get("todos", raw)
            if isinstance(items, list):
                for item in items:
                    parsed.append(
                        {
                            "content": str(item.get("content", "")),
                            "status": str(item.get("status", "pending")),
                            "priority": str(item.get("priority", "medium")),
                        }
                    )
        except Exception:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Error: invalid todos JSON",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        todo_list.clear()
        todo_list.extend(parsed)

        total = len(parsed)
        done = sum(1 for t in parsed if t["status"] == "completed")
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": f"Todo list updated: {done}/{total} completed",
                    }
                ],
                "__todos__": parsed,
            },
            ensure_ascii=False,
        )

    return todowrite
