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
]
