"""Engine-neutral harness event and result types.

A harness run streams a flat sequence of :class:`HarnessEvent` values and
finishes with a :class:`HarnessResult`. Every harness engine (built-in
ReAct agent, pi, DSH, ...) maps its native stream onto this contract so
consumers (the web agent SSE layer, TaskFlow step cards) do not need to
know which engine produced it.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class HarnessEventKind(str, Enum):
    """Engine-neutral progress event kinds."""

    #: A new assistant turn started (one response + its tool calls).
    TURN_START = "turn_start"
    #: Streaming public assistant text, separate from private reasoning.
    TEXT_DELTA = "text_delta"
    #: Streaming reasoning delta from the model.
    THINKING_DELTA = "thinking_delta"
    #: A tool call was requested by the model.
    TOOL_CALL = "tool_call"
    #: Tool execution started.
    TOOL_START = "tool_start"
    #: Tool reported a partial result while running.
    TOOL_OUTPUT = "tool_output"
    #: Tool execution finished (data carries ``is_error``/``duration_ms``).
    TOOL_END = "tool_end"
    #: The authoritative completed assistant message arrived.
    MESSAGE_END = "message_end"
    #: One assistant turn (response + resulting tool calls) finished.
    TURN_END = "turn_end"
    #: The engine is retrying the model call (transient failure).
    RETRY = "retry"
    #: The engine is compacting / reorganizing session context.
    COMPACTING = "compacting"
    #: Misc status update (data carries engine-defined detail).
    STATUS = "status"
    #: The run ended; no automatic work remains (data carries ``aborted``).
    SETTLED = "settled"
    #: A run-level error occurred (data carries ``error``).
    ERROR = "error"


@dataclass
class HarnessEvent:
    """One engine-neutral progress event."""

    kind: HarnessEventKind
    #: Display text (delta text, tool output excerpt, error message, ...).
    text: str = ""
    #: Tool name for tool-related events.
    tool_name: str = ""
    #: 1-based assistant turn counter (engine-specific counting).
    round: int = 0
    #: Engine-defined extra fields.
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging / wire transport."""
        return {
            "kind": self.kind.value,
            "text": self.text,
            "tool_name": self.tool_name,
            "round": self.round,
            "data": self.data,
        }


@dataclass
class HarnessResult:
    """Final outcome of a harness run."""

    #: Final assistant answer text.
    final_text: str = ""
    #: True when the run was aborted (user or timeout) rather than completed.
    aborted: bool = False
    #: Populated when the run ended due to an engine-level error.
    error: Optional[str] = None
    #: Number of assistant turns consumed.
    rounds: int = 0
    #: Engine-defined metrics (tokens, cost, duration, ...).
    usage: Dict[str, Any] = field(default_factory=dict)


class HarnessError(RuntimeError):
    """A harness engine failed to run the task."""


class PiProcessDeadError(HarnessError):
    """The pi RPC subprocess died unexpectedly."""
