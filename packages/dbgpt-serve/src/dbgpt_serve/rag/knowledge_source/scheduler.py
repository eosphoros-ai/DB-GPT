"""Due-binding sync scheduler (modeled on the wiki task scheduler)."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from dbgpt_serve.rag.knowledge_source.service import KnowledgeSourceService

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60.0

_current_scheduler: Optional["KnowledgeSourceScheduler"] = None


def get_knowledge_source_scheduler() -> Optional["KnowledgeSourceScheduler"]:
    return _current_scheduler


class KnowledgeSourceScheduler:
    """Every minute: recover stale runs, then sync due active bindings."""

    def __init__(
        self,
        service: KnowledgeSourceService,
        poll_interval: float = POLL_INTERVAL_SECONDS,
    ):
        self._service = service
        self._poll_interval = poll_interval
        self._loop_task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        global _current_scheduler
        if self._loop_task is not None:
            return
        recovered = self._service._dao.recover_stale_running()
        if recovered:
            logger.info(
                f"knowledge-source scheduler recovered {recovered} stale binding(s)"
            )
        self._stopped = asyncio.Event()
        self._loop_task = asyncio.get_event_loop().create_task(self._run_loop())
        _current_scheduler = self

    async def stop(self) -> None:
        global _current_scheduler
        if self._loop_task is not None:
            self._stopped.set()
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):  # noqa: B014
                pass
            self._loop_task = None
        if _current_scheduler is self:
            _current_scheduler = None

    async def _run_loop(self) -> None:
        logger.info("knowledge-source scheduler started")
        while not self._stopped.is_set():
            try:
                due = self._service._dao.due_sources()
                for source in due:
                    # claim inside run_sync; sequential on purpose (P0)
                    summary = await self._service.run_sync(
                        source.id, trigger="scheduler"
                    )
                    logger.info(
                        "knowledge-source %s scheduled sync: %s +created=%s/updated=%s",
                        source.id,
                        summary["status"],
                        summary["items_created"],
                        summary["items_updated"],
                    )
                if not due:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("knowledge-source scheduler loop error")
                await asyncio.sleep(self._poll_interval)
        logger.info("knowledge-source scheduler stopped")
