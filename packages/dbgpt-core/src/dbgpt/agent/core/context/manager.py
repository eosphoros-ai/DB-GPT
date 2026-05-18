"""Context manager that orchestrates multi-layer compaction."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, Optional

from .budget import ContextBudgetConfig, ContextBudgetTracker, TokenState
from .compact import (
    FullContextCompression,
    ObservationMicroCompact,
    ReactiveCompact,
    SessionMemoryCompact,
)

if TYPE_CHECKING:
    from dbgpt.agent.core.agent import AgentMessage
    from dbgpt.agent.util.llm.llm_client import AIWrapper

logger = logging.getLogger(__name__)

# Type alias for the async callback that receives context status updates.
# Signature: async def callback(status: Dict[str, Any]) -> None
ContextStatusCallback = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class ContextManager:
    """Orchestrates progressive multi-layer context compaction.

    Layers are applied in order of increasing aggressiveness:
      - Layer 1 (WARNING):  ObservationMicroCompact — truncate old observations
      - Layer 2 (WARNING):  SessionMemoryCompact — drop old rounds
      - Layer 3 (ERROR):    FullContextCompression — LLM summary
      - Layer 4 (reactive): ReactiveCompact — emergency last-resort trim
    """

    def __init__(
        self,
        config: Optional[ContextBudgetConfig] = None,
        model_name: Optional[str] = None,
        llm_client: Optional["AIWrapper"] = None,
        on_status_event: Optional[ContextStatusCallback] = None,
    ):
        self.config = config or ContextBudgetConfig()
        self.tracker = ContextBudgetTracker(self.config, model_name=model_name)
        self.llm_client = llm_client
        self.on_status_event = on_status_event

        self._layer1 = ObservationMicroCompact()
        self._layer2 = SessionMemoryCompact()
        self._layer3 = FullContextCompression()
        self._layer4 = ReactiveCompact()

    async def _emit_status(
        self,
        token_count: int,
        state: TokenState,
        compact_layer: Optional[str] = None,
    ) -> None:
        """Push a context.status event to the registered callback (if any)."""
        budget = self.tracker.config.effective_budget
        if budget <= 0:
            logger.debug(
                "Skip context status emit because effective budget is non-positive: %d",
                budget,
            )
            return
        ratio = round(token_count / budget, 4) if budget > 0 else 1.0
        logger.info(
            "Context status: tokens=%d, budget=%d, ratio=%.4f, state=%s, layer=%s",
            token_count,
            budget,
            ratio,
            state.value,
            compact_layer or "none",
        )
        if self.on_status_event is None:
            return
        try:
            await self.on_status_event(
                {
                    "type": "context.status",
                    "used": token_count,
                    "budget": budget,
                    "ratio": ratio,
                    "state": state.value,
                    "compact_layer": compact_layer,
                }
            )
        except Exception:
            logger.debug("Failed to emit context status event", exc_info=True)

    async def manage_context(
        self,
        messages: List["AgentMessage"],
        current_round: int,
        task_progress: Optional[str] = None,
    ) -> List["AgentMessage"]:
        """Apply progressive compaction based on current token budget state.

        Args:
            messages: The full list of agent messages (system + conversation).
            current_round: Current retry/round counter.
            task_progress: The task_progress_summary string (already in system
                prompt, used by Layer 2 as implicit summary).

        Returns:
            Possibly compacted list of messages.
        """
        token_count = self.tracker.count_messages(messages)
        self.tracker.record_token_count(token_count)
        state = self.tracker.get_state(token_count)

        # Always emit current status so the frontend can show the progress bar
        logger.warning(
            "[CTX-DEBUG] manage_context called: tokens=%d, state=%s, callback=%s",
            token_count,
            state.value,
            self.on_status_event is not None,
        )
        await self._emit_status(token_count, state)

        if state == TokenState.NORMAL:
            return messages

        if self.tracker.circuit_breaker_tripped:
            logger.warning(
                "Context compaction circuit breaker tripped — skipping compaction"
            )
            return messages

        logger.info(
            "Context management triggered: state=%s, tokens=%d, budget=%d",
            state.value,
            token_count,
            self.tracker.config.effective_budget,
        )

        # Layer 1: truncate old observations
        if state >= TokenState.WARNING:
            messages = self._layer1.compact(messages, current_round, self.tracker)
            token_count = self.tracker.count_messages(messages)
            state = self.tracker.get_state(token_count)
            await self._emit_status(token_count, state, compact_layer="layer1")

        # Layer 2: drop old rounds (no LLM needed)
        if state >= TokenState.WARNING:
            messages = self._layer2.compact(messages, task_progress, self.tracker)
            token_count = self.tracker.count_messages(messages)
            state = self.tracker.get_state(token_count)
            await self._emit_status(token_count, state, compact_layer="layer2")

        # Layer 3: LLM-based summarization
        if state >= TokenState.ERROR and self.llm_client is not None:
            try:
                messages = await self._layer3.compact(
                    messages, self.llm_client, self.tracker
                )
                self.tracker.record_compact_success()
                token_count = self.tracker.count_messages(messages)
                state = self.tracker.get_state(token_count)
                await self._emit_status(token_count, state, compact_layer="layer3")
            except Exception:
                self.tracker.record_compact_failure()
                logger.exception("Layer 3 compaction failed")

        return messages

    async def reactive_compact(
        self, messages: List["AgentMessage"]
    ) -> List["AgentMessage"]:
        """Emergency compaction triggered by context_too_long errors."""
        logger.warning("Reactive compaction triggered (Layer 4)")
        messages = self._layer4.compact(messages, self.tracker)
        token_count = self.tracker.count_messages(messages)
        state = self.tracker.get_state(token_count)
        await self._emit_status(token_count, state, compact_layer="layer4")
        return messages
