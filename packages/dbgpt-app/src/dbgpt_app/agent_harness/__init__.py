"""Pluggable agent harness engines for DB-GPT.

A *harness* is the execution container above the model: it owns the agent
loop, tools, and session state. DB-GPT ships one built-in harness (its own
``ToolCallingReActAgent``) and can delegate a whole run to external harness
engines (pi, DSH). Callers stream neutral :class:`HarnessEvent` progress
events instead of engine-specific ones.
"""

from .base import (
    HarnessError,
    HarnessEvent,
    HarnessEventKind,
    HarnessResult,
    PiProcessDeadError,
)
from .registry import HARNESS_RUNNER_REGISTRY, HarnessRunnerRegistry

__all__ = [
    "HarnessError",
    "HarnessEvent",
    "HarnessEventKind",
    "HarnessResult",
    "PiProcessDeadError",
    "HARNESS_RUNNER_REGISTRY",
    "HarnessRunnerRegistry",
]
