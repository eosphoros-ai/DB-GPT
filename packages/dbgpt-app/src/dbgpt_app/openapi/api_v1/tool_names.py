"""Canonical tool names and historical aliases.

The shell / code tools were renamed ``shell_interpreter`` -> ``bash`` and
``code_interpreter`` -> ``code``. Stored L2 rules / overrides, replayed
conversation steps and model habits from before the rename still carry the
old strings, so every name comparison goes through :func:`canonical_tool`.
"""

TOOL_ALIASES = {
    "shell_interpreter": "bash",
    "code_interpreter": "code",
}


def canonical_tool(name: str) -> str:
    """Map a historical tool name to its canonical one (idempotent)."""
    return TOOL_ALIASES.get(name, name)
