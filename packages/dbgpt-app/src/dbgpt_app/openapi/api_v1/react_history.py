"""Build prior-turn ReAct history for a follow-up request.

Each HTTP call to ``chat_react_agent`` constructs a new ``ReActAgent`` whose
short-term memory starts empty. Tool-step fragments recovered from GPTs
message storage (if any) are also truncated by a 5-slot buffer, so the
previous *user question* and *final answer* are usually missing from the
LLM prompt.

ReAct's thinking step treats the last Human message as the task
(``Observation: ...``). Extra Human/AI turns can be ignored or even
re-executed as a new task. Completed turns are therefore folded into that
single current question, with only ``final_content`` (not prior SQL traces).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 8
DEFAULT_MAX_ANSWER_CHARS = 4000

_HISTORY_HINT = """
## Previous conversation
When the user message contains "Prior turns in this conversation", those
turns already happened in this same chat. Use them to resolve references
such as "上面", "刚才", "the order above", or "that product". Answer the
## Current question only; do not redo a prior turn unless the user asks.
"""


def extract_react_final_content(
    raw: str, max_chars: int = DEFAULT_MAX_ANSWER_CHARS
) -> str:
    """Prefer ``final_content`` from a persisted react-agent view payload."""
    text = (raw or "").strip()
    if text.startswith("{") and "final_content" in text:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict) and "final_content" in payload:
                final_content = payload["final_content"]
                text = str(final_content).strip() if final_content is not None else ""
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.debug("Failed to parse react-agent view payload as JSON")
    if max_chars > 0 and len(text) > max_chars:
        if max_chars <= 3:
            text = text[:max_chars]
        else:
            text = text[: max_chars - 3] + "..."
    return text


def _message_role(msg: Any) -> str:
    role = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
    return str(role).lower()


def _message_text(msg: Any) -> str:
    last_text = getattr(msg, "last_text", None)
    if isinstance(last_text, str):
        return last_text.strip()
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content.strip()
    return str(content or "").strip()


def completed_turn_pairs(
    messages: Optional[Iterable[Any]],
    current_user_input: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_answer_chars: int = DEFAULT_MAX_ANSWER_CHARS,
) -> List[Tuple[str, str]]:
    """Return ``(question, final_answer)`` for completed prior turns."""
    current = (current_user_input or "").strip()
    pairs: List[Tuple[str, str]] = []
    pending_q: Optional[str] = None
    for msg in messages or []:
        role = _message_role(msg)
        text = _message_text(msg)
        if not text:
            continue
        if role == "human":
            pending_q = text
            continue
        if role in ("view", "ai") and pending_q:
            answer = extract_react_final_content(text, max_answer_chars)
            if pending_q and answer:
                pairs.append((pending_q, answer))
            pending_q = None
    # The current round's user message is appended before the agent runs.
    if pending_q is not None and pending_q == current:
        pending_q = None
    if max_turns > 0:
        pairs = pairs[-max_turns:]
    return pairs


def format_react_followup_question(
    current_user_input: str,
    messages: Optional[Sequence[Any]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_answer_chars: int = DEFAULT_MAX_ANSWER_CHARS,
) -> str:
    """Fold prior Q/A into the current user text (the ReAct Observation).

    First-turn requests with no completed history are returned unchanged so
    stored ``user_input`` and the model question stay aligned.
    """
    current = current_user_input or ""
    pairs = completed_turn_pairs(
        messages,
        current,
        max_turns=max_turns,
        max_answer_chars=max_answer_chars,
    )
    if not pairs:
        return current
    lines = ["## Prior turns in this conversation"]
    for idx, (question, answer) in enumerate(pairs, start=1):
        lines.append(f"Turn {idx} user: {question}")
        lines.append(f"Turn {idx} assistant: {answer}")
    lines.append("")
    lines.append("## Current question")
    lines.append(current)
    return "\n".join(lines)


def history_prompt_hint(has_prior_turns: bool) -> str:
    """Extra system-prompt paragraph when prior turns are present."""
    if not has_prior_turns:
        return ""
    return _HISTORY_HINT
