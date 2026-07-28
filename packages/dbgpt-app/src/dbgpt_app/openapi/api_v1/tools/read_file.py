"""read_file tool — read persisted tool output or snapshot files from disk.

When a tool result is too large for the LLM context window, the
``ToolResultStorage`` writes the full output to disk and replaces the
in-context content with a ``<persisted-output>`` preview block that includes
the file path. This tool lets the agent read back that file (with pagination)
so it can access the full content on demand.

It also reads operation snapshot files written by ``Role._write_op_snapshot``,
which previously had no corresponding read action.

Security: only files under the ``persisted_results/`` or ``op_snapshots/``
directories (within the configured ``output_dir`` or ``DBGPT_HOME/workspace``)
may be read, preventing path traversal.
"""

import json
import os
from typing import Annotated, Any, Dict

from dbgpt.agent.resource.tool.base import tool


def _resolve_allowed_dirs(react_state: Dict[str, Any]) -> list:
    """Return the list of directories the read_file tool may read from."""
    allowed = []
    # Prefer an explicit output_dir if the agent context set one.
    output_dir = react_state.get("output_dir")
    if output_dir:
        allowed.append(os.path.join(output_dir, "persisted_results"))
        allowed.append(os.path.join(output_dir, "op_snapshots"))
    # Always allow the DBGPT_HOME/workspace default locations so read_file
    # works even when output_dir was not propagated into react_state.
    home = os.environ.get("DBGPT_HOME", os.path.expanduser("~/.dbgpt"))
    workspace = os.path.join(home, "workspace")
    allowed.append(os.path.join(workspace, "persisted_results"))
    allowed.append(os.path.join(workspace, "op_snapshots"))
    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for d in allowed:
        rd = os.path.realpath(d)
        if rd not in seen:
            seen.add(rd)
            unique.append(rd)
    return unique


def _is_within_allowed(file_path: str, allowed_dirs: list) -> bool:
    try:
        real_path = os.path.realpath(file_path)
    except Exception:
        return False
    for d in allowed_dirs:
        if real_path == d or real_path.startswith(d + os.sep):
            return True
    return False


def make_read_file(react_state: Dict[str, Any]):
    """Create a read_file tool bound to the given react_state.

    react_state is expected to contain ``conv_id`` (used for tracing) and
    optionally ``output_dir``. The allowed read directories are derived from
    these so the tool can locate persisted results written by the agent.
    """

    @tool(
        "read_file",
        description=(
            "Read a file from disk with pagination. Use this when you see a "
            "<persisted-output> block with a file path and need to access the "
            "full content, or when you need to read an operation snapshot. "
            "Supports offset/limit for reading specific sections of large files. "
            'Parameters: {"file_path": "absolute path from <persisted-output> block", '
            '"offset": "start line number, 0-based (optional, default 0)", '
            '"limit": "max lines to read (optional, default 100)"}'
        ),
    )
    def read_file(
        file_path: Annotated[str, "Absolute path to the file to read"],
        offset: Annotated[int, "Start line number (0-based)"] = 0,
        limit: Annotated[int, "Max lines to read"] = 100,
    ) -> str:
        """Read a file from disk with pagination."""
        allowed_dirs = _resolve_allowed_dirs(react_state)
        if not _is_within_allowed(file_path, allowed_dirs):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                "Access denied: file path must be within the "
                                "persisted_results or op_snapshots directories."
                            ),
                        }
                    ]
                },
                ensure_ascii=False,
            )

        if not os.path.isfile(file_path):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                f"File not found: {file_path}. The persisted "
                                "result may have been cleaned up."
                            ),
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "text", "content": f"Error reading file: {e}"}
                    ]
                },
                ensure_ascii=False,
            )

        total_lines = len(lines)
        start = max(0, int(offset))
        end = min(start + max(1, int(limit)), total_lines)
        selected = lines[start:end]

        result_lines = [
            f"File: {file_path} ({total_lines} lines, showing {start + 1}-{end})"
        ]
        for i, line in enumerate(selected):
            result_lines.append(f"  {start + i + 1:>4} | {line.rstrip()}")

        if end < total_lines:
            result_lines.append(
                f"  ... ({total_lines - end} more lines, use offset={end} to continue)"
            )

        content = "\n".join(result_lines)
        return json.dumps(
            {"chunks": [{"output_type": "text", "content": content}]},
            ensure_ascii=False,
        )

    return read_file
