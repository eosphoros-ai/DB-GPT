"""Durable wiki task scheduler.

Replaces WeKnora's asynq + Redis + dedicated worker pool with a single
in-process asyncio worker driven by the ``knowledge_wiki_task`` table:

- Document sync enqueue -> debounced (30s) ``wiki:ingest`` per space
- Ingest close-out      -> debounced (20s) ``wiki:finalize`` per space
- Document delete       -> ``wiki:reconcile`` (cross-link / reference rework)

Startup recovers tasks stuck in ``running`` (process restart) back to
``pending``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional

from dbgpt_serve.rag.models.wiki_db import KnowledgeWikiTaskDao
from dbgpt_serve.rag.service.wiki.config import WikiSpaceConfig

logger = logging.getLogger(__name__)

WIKI_INGEST_DEBOUNCE_SECONDS = 30.0
WIKI_FINALIZE_DEBOUNCE_SECONDS = 20.0
POLL_INTERVAL_SECONDS = 5.0
BATCH_SIZE = 3

# Module-level handle so service hooks / endpoints can enqueue without
# threading the scheduler through every layer.
_current_scheduler: Optional["WikiTaskScheduler"] = None


def get_wiki_scheduler() -> Optional["WikiTaskScheduler"]:
    return _current_scheduler


def set_wiki_scheduler(scheduler: Optional["WikiTaskScheduler"]) -> None:
    global _current_scheduler
    _current_scheduler = scheduler


class WikiTaskScheduler:
    """Polls the task table and dispatches to wiki pipeline handlers."""

    def __init__(
        self,
        system_app: Any,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        batch_size: int = BATCH_SIZE,
    ):
        self._system_app = system_app
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._loop_task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()
        self._handlers: Dict[
            str, Callable[[WikiSpaceConfig, Dict[str, Any]], Awaitable[None]]
        ] = {}

        self._task_dao = KnowledgeWikiTaskDao()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def register_handler(
        self,
        task_type: str,
        handler: Callable[[WikiSpaceConfig, Dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._handlers[task_type] = handler

    def start(self) -> None:
        if self._loop_task is not None:
            return
        recovered = self._task_dao.recover_stale_running()
        if recovered:
            logger.info(f"wiki scheduler recovered {recovered} stale running task(s)")
        self._stopped = asyncio.Event()
        self._loop_task = asyncio.get_event_loop().create_task(self._run_loop())
        set_wiki_scheduler(self)

    async def stop(self) -> None:
        if self._loop_task is not None:
            self._stopped.set()
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):  # noqa: B014
                pass
            self._loop_task = None
        if _current_scheduler is self:
            set_wiki_scheduler(None)

    # ------------------------------------------------------------------
    # Enqueue helpers (used by service hooks and endpoints)
    # ------------------------------------------------------------------
    def enqueue_ingest(self, space_id: int, document_ids=None) -> None:
        self._task_dao.enqueue(
            space_id,
            "wiki:ingest",
            payload={},
            delay_seconds=WIKI_INGEST_DEBOUNCE_SECONDS,
            merge_document_ids=document_ids,
        )

    def enqueue_ingest_soon(
        self, space_id: int, document_ids, delay_seconds: float = 2.0
    ) -> None:
        """Short-delay variant for explicit user actions (e.g. enable)."""
        self._task_dao.enqueue(
            space_id,
            "wiki:ingest",
            payload={},
            delay_seconds=delay_seconds,
            merge_document_ids=document_ids,
        )

    def enqueue_finalize(self, space_id: int) -> None:
        self._task_dao.enqueue(
            space_id,
            "wiki:finalize",
            payload={},
            delay_seconds=WIKI_FINALIZE_DEBOUNCE_SECONDS,
        )

    def enqueue_reconcile(self, space_id: int, deleted_document_id: int) -> None:
        self._task_dao.enqueue(
            space_id,
            "wiki:reconcile",
            payload={"deleted_document_id": deleted_document_id},
            delay_seconds=5,
        )

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    async def _run_loop(self) -> None:
        logger.info("wiki task scheduler started")
        while not self._stopped.is_set():
            try:
                claimed = await self._claim_once()
                if not claimed:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("wiki scheduler loop error:\n" + traceback.format_exc())
                await asyncio.sleep(self._poll_interval)
        logger.info("wiki task scheduler stopped")

    async def _claim_once(self) -> int:
        tasks = self._task_dao.claim_due_tasks(self._batch_size)
        for task in tasks:
            try:
                await self._dispatch(task)
            except Exception as exc:
                logger.error(
                    f"wiki task #{task.id} ({task.task_type}) failed: {exc}\n"
                    + traceback.format_exc()
                )
                self._task_dao.complete_task(task.id, error=str(exc))
            else:
                self._task_dao.complete_task(task.id)
                if task.task_type == "wiki:ingest":
                    self.enqueue_finalize(task.space_id)
        return len(tasks)

    async def _dispatch(self, task: Any) -> None:
        handler = self._handlers.get(task.task_type)
        if handler is None:
            raise ValueError(f"no handler for task type {task.task_type}")
        from dbgpt_serve.rag.models.models import KnowledgeSpaceDao

        space_dao = KnowledgeSpaceDao()
        spaces = space_dao.get_knowledge_space_by_ids([task.space_id])
        if not spaces:
            logger.warning(f"wiki task #{task.id}: space {task.space_id} missing, skip")
            return
        cfg = WikiSpaceConfig.from_space(spaces[0])
        if not cfg.enabled:
            logger.warning(
                f"wiki task #{task.id}: space {task.space_id} wiki disabled, skip"
            )
            return
        payload = {}
        if task.payload:
            try:
                payload = json.loads(task.payload)
            except (TypeError, ValueError):
                payload = {}
        await handler(cfg, payload)
