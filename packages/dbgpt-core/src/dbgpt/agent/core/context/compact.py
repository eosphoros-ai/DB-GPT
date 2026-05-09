"""Four-layer compaction strategies for context management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from dbgpt.core import ModelMessageRoleType

from .budget import ContextBudgetTracker

if TYPE_CHECKING:
    from dbgpt.agent.core.agent import AgentMessage
    from dbgpt.agent.util.llm.llm_client import AIWrapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUMMARY_PROMPT = """\
You are a context summarizer for a ReAct agent. Condense the conversation history \
into a structured summary. Be precise — preserve exact names, paths, values, and \
variable names.

## Conversation to summarize
{conversation_text}

## Output format (use exactly these headings)
1. Original Task: <one-line description>
2. Completed Steps: <one line per step, action + key result>
3. Current State: <what the agent currently knows>
4. Key Data: <important values, paths, variable names — must be exact>
5. Errors Encountered: <failures and how they were resolved, or "None">
6. Next Steps: <remaining work, or "None" if task is complete>
"""


def _is_observation_message(msg: "AgentMessage") -> bool:
    """Check if a message is an Observation (tool output) in ReAct format."""
    content = getattr(msg, "content", "") or ""
    role = getattr(msg, "role", None)
    return role == ModelMessageRoleType.HUMAN and content.lstrip().startswith(
        "Observation:"
    )


def _is_system_message(msg: "AgentMessage") -> bool:
    """Check if a message has the SYSTEM role."""
    return getattr(msg, "role", None) == ModelMessageRoleType.SYSTEM


def _detect_round_boundaries(messages: List["AgentMessage"]) -> List[List[int]]:
    """Detect ReAct triplet (Thought/Action/Observation) round boundaries.

    Returns a list of rounds, where each round is a list of message indices
    belonging to that round. System messages are excluded.
    """
    rounds: List[List[int]] = []
    current_round: List[int] = []

    for idx, msg in enumerate(messages):
        if _is_system_message(msg):
            continue

        current_round.append(idx)

        # An Observation message marks the end of a ReAct triplet
        if _is_observation_message(msg):
            rounds.append(current_round)
            current_round = []

    # Remaining messages that don't form a complete triplet
    if current_round:
        rounds.append(current_round)

    return rounds


# ---------------------------------------------------------------------------
# Layer 1: ObservationMicroCompact
# ---------------------------------------------------------------------------


class ObservationMicroCompact:
    """Layer 1 — truncate old Observation messages.

    The lightest compaction: shorten tool outputs from old rounds while
    preserving recent ones in full.
    """

    def compact(
        self,
        messages: List["AgentMessage"],
        current_round: int,
        tracker: ContextBudgetTracker,
    ) -> List["AgentMessage"]:
        cfg = tracker.config
        cutoff_round = current_round - cfg.max_observation_age_rounds
        max_chars = cfg.truncated_observation_max_chars

        rounds = _detect_round_boundaries(messages)
        truncated = 0

        for round_idx, indices in enumerate(rounds):
            if round_idx >= cutoff_round:
                break
            for msg_idx in indices:
                msg = messages[msg_idx]
                if _is_observation_message(msg):
                    content = msg.content or ""
                    if len(content) > max_chars + 30:
                        snapshot_path = None
                        ctx = getattr(msg, "context", None)
                        if isinstance(ctx, dict):
                            snapshot_path = ctx.get("snapshot_path")
                        suffix = (
                            f"... [truncated, full detail at: {snapshot_path}]"
                            if snapshot_path
                            else "... [truncated]"
                        )
                        msg.content = content[:max_chars] + suffix
                        truncated += 1

        if truncated:
            logger.info(
                "Layer 1 (ObservationMicroCompact): truncated %d old observations",
                truncated,
            )
        return messages


# ---------------------------------------------------------------------------
# Layer 2: SessionMemoryCompact
# ---------------------------------------------------------------------------


class SessionMemoryCompact:
    """Layer 2 — drop old rounds, rely on task_progress as implicit summary.

    No LLM call needed because the system prompt already contains
    ``{{ task_progress }}`` with a record of every completed step.
    """

    def compact(
        self,
        messages: List["AgentMessage"],
        task_progress: Optional[str],
        tracker: ContextBudgetTracker,
    ) -> List["AgentMessage"]:
        cfg = tracker.config

        # Separate system messages from conversation messages
        system_msgs = [m for m in messages if _is_system_message(m)]
        conv_msgs = [m for m in messages if not _is_system_message(m)]

        if not conv_msgs:
            return messages

        rounds = _detect_round_boundaries(conv_msgs)
        if len(rounds) <= cfg.min_keep_recent_rounds:
            return messages

        # Work backwards: keep at least min_keep_recent_rounds
        keep_from = len(rounds) - cfg.min_keep_recent_rounds

        # Also keep enough rounds so we retain min_keep_tokens
        kept_tokens = 0
        for r_idx in range(len(rounds) - 1, -1, -1):
            round_tokens = sum(
                tracker.count_messages([conv_msgs[i]]) for i in rounds[r_idx]
            )
            kept_tokens += round_tokens
            if r_idx < keep_from and kept_tokens >= cfg.min_keep_tokens:
                break
            keep_from = min(keep_from, r_idx)

        if keep_from <= 0:
            return messages

        # Collect indices to keep (complete triplets only)
        keep_indices = set()
        for r_idx in range(keep_from, len(rounds)):
            for i in rounds[r_idx]:
                keep_indices.add(id(conv_msgs[i]))

        kept_conv = [m for m in conv_msgs if id(m) in keep_indices]

        dropped = len(conv_msgs) - len(kept_conv)
        if dropped > 0:
            logger.info(
                "Layer 2 (SessionMemoryCompact): dropped %d messages "
                "(%d rounds), keeping %d recent rounds",
                dropped,
                keep_from,
                len(rounds) - keep_from,
            )

        return system_msgs + kept_conv


# ---------------------------------------------------------------------------
# Layer 3: FullContextCompression
# ---------------------------------------------------------------------------


class FullContextCompression:
    """Layer 3 — LLM-generated structured summary replaces old messages."""

    async def compact(
        self,
        messages: List["AgentMessage"],
        llm_client: "AIWrapper",
        tracker: ContextBudgetTracker,
    ) -> List["AgentMessage"]:
        from dbgpt.agent.core.agent import AgentMessage

        cfg = tracker.config

        system_msgs = [m for m in messages if _is_system_message(m)]
        conv_msgs = [m for m in messages if not _is_system_message(m)]

        if not conv_msgs:
            return messages

        rounds = _detect_round_boundaries(conv_msgs)
        # Keep last N rounds as-is
        keep_rounds = min(cfg.min_keep_recent_rounds, len(rounds))
        if keep_rounds >= len(rounds):
            return messages

        split = len(rounds) - keep_rounds
        old_indices = set()
        for r_idx in range(split):
            for i in rounds[r_idx]:
                old_indices.add(i)

        old_msgs = [conv_msgs[i] for i in sorted(old_indices)]
        recent_msgs = [
            conv_msgs[i] for i in range(len(conv_msgs)) if i not in old_indices
        ]

        # Build conversation text for summarization
        conv_lines = []
        for msg in old_msgs:
            role = getattr(msg, "role", "unknown")
            content = (getattr(msg, "content", "") or "")[:3000]
            conv_lines.append(f"[{role}]: {content}")
        conversation_text = "\n".join(conv_lines)

        prompt = _SUMMARY_PROMPT.format(conversation_text=conversation_text)

        try:
            summary_text = await llm_client.generate_llm_text(
                prompt, max_new_tokens=2000
            )
        except Exception:
            logger.exception("Layer 3 (FullContextCompression): LLM summary failed")
            raise

        summary_msg = AgentMessage(
            content=f"[Context Summary of {len(old_msgs)} earlier messages]\n\n"
            + summary_text,
            role=ModelMessageRoleType.HUMAN,
        )

        logger.info(
            "Layer 3 (FullContextCompression): summarized %d messages into "
            "1 summary message, keeping %d recent messages",
            len(old_msgs),
            len(recent_msgs),
        )

        return system_msgs + [summary_msg] + recent_msgs


# ---------------------------------------------------------------------------
# Layer 4: ReactiveCompact
# ---------------------------------------------------------------------------


class ReactiveCompact:
    """Layer 4 — emergency compaction when LLM returns context_too_long.

    Keeps only system prompt + the last 2 rounds. The task_progress in the
    system prompt ensures the agent still knows its history.
    """

    def compact(
        self,
        messages: List["AgentMessage"],
        tracker: ContextBudgetTracker,
    ) -> List["AgentMessage"]:
        system_msgs = [m for m in messages if _is_system_message(m)]
        conv_msgs = [m for m in messages if not _is_system_message(m)]

        if not conv_msgs:
            return messages

        rounds = _detect_round_boundaries(conv_msgs)
        keep_rounds = min(2, len(rounds))

        if keep_rounds >= len(rounds):
            return messages

        keep_indices = set()
        for r_idx in range(len(rounds) - keep_rounds, len(rounds)):
            for i in rounds[r_idx]:
                keep_indices.add(i)

        kept = [conv_msgs[i] for i in sorted(keep_indices)]

        dropped = len(conv_msgs) - len(kept)
        logger.warning(
            "Layer 4 (ReactiveCompact): emergency drop of %d messages, "
            "keeping last %d rounds",
            dropped,
            keep_rounds,
        )

        return system_msgs + kept
