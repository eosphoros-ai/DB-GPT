"""Conv-scoped harness runner registry.

Keeps one runner instance per conversation so external
harness engines keep their session context between turns of
the same conversation. Simple LRU cap guards against runner
proliferation.
"""

import asyncio
import logging
from collections import OrderedDict
from typing import Callable, Optional, Tuple

from .pi.config import PiHarnessConfig
from .pi.runner import PiHarnessRunner

logger = logging.getLogger(__name__)

_MAX_RUNNERS = 64


class HarnessRunnerRegistry:
    """conv_id -> runner, engine-scoped."""

    def __init__(self, max_runners: int = _MAX_RUNNERS):
        self._max = max_runners
        self._runners: "OrderedDict[Tuple[str, str], PiHarnessRunner]" = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(
        self,
        engine: str,
        conv_id: str,
        config_factory: Callable[[], PiHarnessConfig],
    ) -> PiHarnessRunner:
        """Get or create the runner for one (engine, conv).

        Only the pi engine is wired today; other engines
        raise :class:`HarnessError` until their runners land.
        """
        from .base import HarnessError

        if engine != "pi":
            raise HarnessError(f"unknown harness engine: {engine}")
        key = (engine, conv_id)
        async with self._lock:
            runner = self._runners.get(key)
            if runner is None or runner._closed:
                runner = PiHarnessRunner(config_factory(), conv_id)
                self._runners[key] = runner
            else:
                self._runners.move_to_end(key)
            while len(self._runners) > self._max:
                _, evicted = self._runners.popitem(last=False)
                try:
                    await evicted.dispose()
                except Exception as e:  # pragma: no cover
                    logger.warning("harness runner dispose failed: %s", e)
            return runner

    async def pop(self, engine: str, conv_id: str) -> Optional[PiHarnessRunner]:
        """Drop (and close) the runner for one conv, if any."""
        key = (engine, conv_id)
        async with self._lock:
            runner = self._runners.pop(key, None)
        if runner is not None:
            try:
                await runner.dispose()
            except Exception as e:  # pragma: no cover
                logger.warning("harness runner dispose failed: %s", e)
        return runner


#: Process-wide registry (the web layer holds one per server).
HARNESS_RUNNER_REGISTRY = HarnessRunnerRegistry()
