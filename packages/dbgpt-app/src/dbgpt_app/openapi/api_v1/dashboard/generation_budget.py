"""A wall-clock budget for a confirmed generation, not for human think time."""

import asyncio
import logging
import os
import time
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)
DEFAULT_GENERATION_TIMEOUT_SECONDS = 180
_active_budget: ContextVar[Optional["GenerationBudget"]] = ContextVar(
    "dashboard_generation_budget", default=None
)


class DashboardGenerationTimeout(TimeoutError):
    """The generation may no longer execute tools or persist a new revision."""


def generation_timeout_seconds() -> int:
    raw = os.getenv("DBGPT_DASHBOARD_GENERATION_TIMEOUT_SECONDS", "180")
    try:
        value = int(raw)
        if 60 <= value <= 300:
            return value
    except (ValueError, TypeError):
        pass
    logger.warning("Invalid Dashboard generation timeout; using 180 seconds")
    return DEFAULT_GENERATION_TIMEOUT_SECONDS


class GenerationBudget:
    def __init__(self, seconds: Optional[float] = None) -> None:
        self.seconds = seconds if seconds is not None else generation_timeout_seconds()
        self.started_at = time.monotonic()
        self.stop_reason: Optional[str] = None

    @property
    def remaining(self) -> float:
        return max(0.0, self.seconds - (time.monotonic() - self.started_at))

    def check(self) -> None:
        if not self.stop_reason and self.remaining <= 0:
            self.stop_reason = "timeout"
        if self.stop_reason:
            raise DashboardGenerationTimeout("Dashboard generation stopped")

    async def run(self, work: Callable[[], Awaitable[Any]]) -> Any:
        token = _active_budget.set(self)
        task = None
        try:
            self.check()
            # Cancel the model/tool await, consume its result, then finish the SSE
            # round. Existing disconnect cleanup continues to own this task.
            task = asyncio.create_task(work())
            done, _ = await asyncio.wait({task}, timeout=self.remaining)
            if not done:
                self.stop_reason = "timeout"
                raise DashboardGenerationTimeout("Dashboard generation timed out")
            # An upstream TimeoutError remains an upstream error, not our timer.
            return task.result()
        except asyncio.CancelledError:
            self.stop_reason = "cancelled"
            raise
        finally:
            if task is not None:
                if not task.done():
                    task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass  # Consume the child; the original outcome propagates.
            _active_budget.reset(token)


def check_generation_deadline() -> None:
    """Also runs immediately before a save; ordinary API edits have no budget."""
    budget = _active_budget.get()
    if budget is not None:
        budget.check()


async def generation_read(work: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Keep blocking read-only drivers off the SSE timer's event loop.

    Cancellation cannot forcibly kill every database driver. A late read may
    finish under its own query timeout, but it cannot reach the save boundary.
    Outside confirmed generation preserve the existing calling/thread behavior.
    """
    if _active_budget.get() is None:
        return work(*args, **kwargs)
    check_generation_deadline()
    result = await asyncio.to_thread(work, *args, **kwargs)
    check_generation_deadline()
    return result
