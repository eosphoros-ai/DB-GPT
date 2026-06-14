"""General-purpose task scheduler based on APScheduler."""

import logging
from typing import Any, Callable, Dict, List, Optional

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import STATE_STOPPED
from apscheduler.triggers.cron import CronTrigger

from dbgpt.component import BaseComponent, SystemApp

logger = logging.getLogger(__name__)

_DEFAULT_JOB_DEFAULTS = {
    "max_instances": 1,
    "coalesce": True,
    "misfire_grace_time": 300,
}


class TaskScheduler(BaseComponent):
    """Singleton task scheduler wrapping AsyncIOScheduler.

    Supports 5-field standard cron and 6-field cron with seconds.
    """

    name = "task_scheduler"

    _instance: Optional["TaskScheduler"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        jobstore_url: str = "sqlite:///scheduler.db",
        system_app: Optional[SystemApp] = None,
    ):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._jobstore_url = jobstore_url
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._build_scheduler()
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Initialize with SystemApp (required by BaseComponent)."""

    def _build_scheduler(self) -> None:
        """Create a fresh AsyncIOScheduler instance.

        Uses MemoryJobStore for in-memory URLs, SQLAlchemyJobStore otherwise.
        """
        if self._jobstore_url == "sqlite:///:memory:":
            self._scheduler = AsyncIOScheduler(job_defaults=_DEFAULT_JOB_DEFAULTS)
        else:
            jobstores = {"default": SQLAlchemyJobStore(url=self._jobstore_url)}
            self._scheduler = AsyncIOScheduler(
                jobstores=jobstores, job_defaults=_DEFAULT_JOB_DEFAULTS
            )

    def _ensure_scheduler(self) -> AsyncIOScheduler:
        """Return the active scheduler instance.

        Raises:
            RuntimeError: If the scheduler has not been started or was shut down.
        """
        if self._scheduler is None:
            raise RuntimeError("TaskScheduler is not started. Call start() first.")
        return self._scheduler

    async def start(self) -> None:
        """Start the scheduler (idempotent)."""
        if self._scheduler is None or self._scheduler.state == STATE_STOPPED:
            self._build_scheduler()
        assert self._scheduler is not None  # guaranteed by _build_scheduler
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("TaskScheduler started.")

    async def shutdown(self) -> None:
        """Shutdown the scheduler and reset singleton."""
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("TaskScheduler shut down.")
        self._scheduler = None
        TaskScheduler._instance = None
        self._initialized = False

    def is_running(self) -> bool:
        """Return whether the scheduler is currently running."""
        if self._scheduler is None:
            return False
        return self._scheduler.running

    async def add_job(
        self,
        job_id: str,
        cron_expression: str,
        func: Callable[..., Any],
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a cron job.

        Args:
            job_id: Unique job identifier.
            cron_expression: 5-field or 6-field cron expression.
            func: Callable to execute.
            kwargs: Keyword arguments passed to func.

        Raises:
            ValueError: If cron_expression is invalid or job_id exists.
        """
        sched = self._ensure_scheduler()
        trigger = self._build_trigger(cron_expression)

        if sched.get_job(job_id) is not None:
            raise ValueError(f"Job {job_id} already exists")

        sched.add_job(
            func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs or {},
            replace_existing=False,
        )

    async def remove_job(self, job_id: str) -> None:
        """Remove a job by ID.

        Raises:
            ValueError: If the job does not exist.
        """
        sched = self._ensure_scheduler()
        try:
            sched.remove_job(job_id)
        except JobLookupError:
            raise ValueError(f"Job {job_id} not found") from None

    def pause_job(self, job_id: str) -> None:
        """Pause a job (keeps definition but stops triggering).

        Raises:
            ValueError: If the job does not exist.
        """
        sched = self._ensure_scheduler()
        try:
            sched.pause_job(job_id)
        except JobLookupError:
            raise ValueError(f"Job {job_id} not found") from None

    def resume_job(self, job_id: str) -> None:
        """Resume a paused job.

        Raises:
            ValueError: If the job does not exist.
        """
        sched = self._ensure_scheduler()
        try:
            sched.resume_job(job_id)
        except JobLookupError:
            raise ValueError(f"Job {job_id} not found") from None

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job by ID, or None if not found.

        Returns:
            A dict with keys ``job_id``, ``next_run_time``, ``name``
            or ``None`` when the job does not exist.
        """
        sched = self._ensure_scheduler()
        job = sched.get_job(job_id)
        if job is None:
            return None
        return {
            "job_id": job.id,
            "next_run_time": (str(job.next_run_time) if job.next_run_time else None),
            "name": job.name,
        }

    def list_jobs(self) -> List[dict]:
        """List all scheduled jobs.

        Returns:
            A list of dicts, each with keys ``job_id``, ``next_run_time``,
            ``name``.
        """
        sched = self._ensure_scheduler()
        return [
            {
                "job_id": job.id,
                "next_run_time": (
                    str(job.next_run_time) if job.next_run_time else None
                ),
                "name": job.name,
            }
            for job in sched.get_jobs()
        ]

    @staticmethod
    def _build_trigger(cron_expression: str) -> CronTrigger:
        """Parse a cron expression into a CronTrigger.

        Supports 5-field (min hour dom mon dow) and
        6-field (sec min hour dom mon dow) formats.

        Raises:
            ValueError: If the expression is invalid.
        """
        parts = cron_expression.strip().split()
        try:
            if len(parts) == 6:
                sec, minute, hour, dom, mon, dow = parts
                return CronTrigger(
                    second=sec,
                    minute=minute,
                    hour=hour,
                    day=dom,
                    month=mon,
                    day_of_week=dow,
                )
            elif len(parts) == 5:
                return CronTrigger.from_crontab(cron_expression)
            else:
                raise ValueError(f"Invalid cron expression: {cron_expression}")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Invalid cron expression: {cron_expression}") from exc
