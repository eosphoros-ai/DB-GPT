"""Multi-layer context management for agent conversations.

This subpackage provides progressive context compaction to prevent token
overflow in long-running ReAct agent sessions.

Layers (applied in order of increasing aggressiveness):
  1. ObservationMicroCompact — truncate old tool outputs
  2. SessionMemoryCompact — drop old rounds (relies on task_progress)
  3. FullContextCompression — LLM-generated summary
  4. ReactiveCompact — emergency last-resort trim
"""

from .budget import ContextBudgetConfig, ContextBudgetTracker, TokenState
from .compact import (
    FullContextCompression,
    ObservationMicroCompact,
    ReactiveCompact,
    SessionMemoryCompact,
)
from .manager import ContextManager, ContextStatusCallback
from .storage import (
    DEFAULT_PREVIEW_SIZE_CHARS,
    DEFAULT_RESULT_SIZE_CHARS,
    DEFAULT_TOOL_RESULT_BUDGET,
    DEFAULT_TURN_BUDGET_CHARS,
    PERSISTED_OUTPUT_CLOSING_TAG,
    PERSISTED_OUTPUT_TAG,
    PINNED_THRESHOLDS,
    ToolResultBudgetConfig,
    ToolResultStorage,
    generate_preview,
    get_current_storage,
    set_current_storage,
    tool_result_budget_for_context_window,
)

__all__ = [
    "TokenState",
    "ContextBudgetConfig",
    "ContextBudgetTracker",
    "ObservationMicroCompact",
    "SessionMemoryCompact",
    "FullContextCompression",
    "ReactiveCompact",
    "ContextManager",
    "ContextStatusCallback",
    "ToolResultStorage",
    "ToolResultBudgetConfig",
    "DEFAULT_TOOL_RESULT_BUDGET",
    "DEFAULT_RESULT_SIZE_CHARS",
    "DEFAULT_TURN_BUDGET_CHARS",
    "DEFAULT_PREVIEW_SIZE_CHARS",
    "PERSISTED_OUTPUT_TAG",
    "PERSISTED_OUTPUT_CLOSING_TAG",
    "PINNED_THRESHOLDS",
    "generate_preview",
    "get_current_storage",
    "set_current_storage",
    "tool_result_budget_for_context_window",
]
