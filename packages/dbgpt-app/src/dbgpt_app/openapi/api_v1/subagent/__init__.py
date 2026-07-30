"""Sub-agent parallel dispatch subpackage.

This package isolates the parallel sub-agent delegation feature for the
``POST /v1/chat/react-agent`` link from the oversized ``agentic_data_api.py``.

Modules:
    react_tools:  ``make_react_tools`` factory — rebuilds the react_state-bound
                  ReAct tools per (sub-)agent, so each agent owns an isolated
                  mutable state container.
    dispatcher:   ``build_sub_react_agent`` + ``make_dispatch_tool`` —
                  constructs isolated child ReActAgents and fans out
                  independent sub-tasks via ``asyncio.gather``.
    result:       sub-agent result relay — compressed text into the lead
                  agent's context, artifacts out-of-band as path references.

Contract (see design spec §4.2 / plan stage 0):

    A single sub-task passed to ``dispatch_parallel_tasks`` is a dict::

        {
            "goal": str,  # required; self-contained objective. The sub-agent
            # cannot see the main conversation history, so the
            # goal must carry every detail it needs (which
            # database/table, which knowledge base, which MCP).
            "context": str,  # optional; upstream results / shared background,
            # spliced into the sub-agent's input.
            "title": str,  # optional; short label for UI display.
        }
"""

from typing import Optional, TypedDict


class SubTask(TypedDict, total=False):
    """A single independent sub-task for ``dispatch_parallel_tasks``.

    Attributes:
        goal: Required. Self-contained objective for the sub-agent.
        context: Optional. Upstream results / shared background.
        title: Optional. Short label for UI display.
    """

    goal: str
    context: Optional[str]
    title: Optional[str]


__all__ = ["SubTask"]
