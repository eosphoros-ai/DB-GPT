"""Build prior-turn ReAct history for a follow-up request.

Each HTTP call to ``chat_react_agent`` constructs a new ``ReActAgent`` whose
short-term memory starts empty. Tool-step fragments recovered from GPTs
message storage (if any) are also truncated by a 5-slot buffer, so the
previous *user question* and *final answer* are usually missing from the
LLM prompt. This module reconstructs those completed turns from
``StorageConversation`` messages so anaphora like "上面" / "that order"
can resolve.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from dbgpt.agent import AgentMessage
from dbgpt.core import ModelMessageRoleType

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 8
DEFAULT_MAX_ANSWER_CHARS = 4000

_HISTORY_HINT = """
## Previous conversation
Messages labeled "Previous question" / "Previous result" are completed
turns in this same conversation. Use them to resolve references such as
"上面", "刚才", "the order above", or "that product". Do not ignore them
and re-solve a prior question from scratch unless the user asks to redo it.
"""


def extract_react_final_content(
    raw: str, max_chars: int = DEFAULT_MAX_ANSWER_CHARS
) -> str:
    """Prefer ``final_content`` from a persisted react-agent view payload."""
    text = (raw or "").strip()
    if text.startswith("{") and "final_content" in text:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict) and payload.get("final_content"):
                text = str(payload["final_content"]).strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.debug("Failed to parse react-agent view payload as JSON")
    if max_chars > 0 and len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return text


def _message_role(msg: Any) -> str:
    role = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
    return str(role).lower()


def _message_text(msg: Any) -> str:
    last_text = getattr(msg, "last_text", None)
    if isinstance(last_text, str):
        return last_text.strip()
    if callable(last_text):
        try:
            value = last_text()
            if isinstance(value, str):
                return value.strip()
        except Exception:
            pass
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content.strip()
    return str(content or "").strip()


def _completed_pairs(
    messages: Optional[Iterable[Any]],
    current_user_input: str,
) -> List[Tuple[str, str]]:
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
            pairs.append((pending_q, text))
            pending_q = None
    # The current round's user message is appended before the agent runs,
    # so it has no view yet — drop it.
    if pending_q is not None and pending_q == current:
        pending_q = None
    return pairs


def build_react_historical_dialogues(
    messages: Optional[Sequence[Any]],
    current_user_input: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_answer_chars: int = DEFAULT_MAX_ANSWER_CHARS,
) -> List[AgentMessage]:
    """Return prior human/assistant turns as ``AgentMessage``s.

    Tool traces from earlier ReAct loops are intentionally omitted; only the
    user question and the persisted final answer are kept.
    """
    pairs = _completed_pairs(messages, current_user_input)
    if max_turns > 0:
        pairs = pairs[-max_turns:]
    dialogues: List[AgentMessage] = []
    for question, raw_answer in pairs:
        answer = extract_react_final_content(raw_answer, max_answer_chars)
        if not question or not answer:
            continue
        dialogues.append(
            AgentMessage(
                content=f"Previous question: {question}",
                role=ModelMessageRoleType.HUMAN,
            )
        )
        dialogues.append(
            AgentMessage(
                content=f"Previous result: {answer}",
                role=ModelMessageRoleType.AI,
            )
        )
    return dialogues


def history_prompt_hint(dialogues: Sequence[AgentMessage]) -> str:
    """Extra system-prompt paragraph when prior turns are present."""
    if not dialogues:
        return ""
    return _HISTORY_HINT
