"""ScheduledTaskServe - mount routes, start scheduler, recover jobs on boot."""

import logging
import os
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import DatabaseManager
from dbgpt.util.scheduler.task_scheduler import TaskScheduler
from dbgpt_serve.core import BaseServe

from .api.endpoints import init_endpoints, router
from .config import (
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)
from .service.chat_replay_runner import run_scheduled_task
from .service.service import ScheduledTaskService

logger = logging.getLogger(__name__)

# Env var name for the master switch that controls whether scheduled tasks
# are actually *executed* on this process. See _scheduler_enabled().
_SCHEDULER_ENABLED_ENV = "DBGPT_CHAT_TASK_SCHEDULER_ENABLED"

# In-memory jobstore sentinel. TaskScheduler treats this exact URL as a signal
# to use APScheduler's MemoryJobStore (no SQLite file, no apscheduler_jobs
# table). The business tables (dbgpt_serve_scheduled_task / _run) are the sole
# source of truth; jobs are rehydrated into memory on boot via
# _recover_jobs_from_db().
_IN_MEMORY_JOBSTORE_URL = "sqlite:///:memory:"


def _scheduler_enabled() -> bool:
    """Env-driven master switch for *executing* scheduled tasks.

    Controls rehydrate + triggering only — the REST API is always mounted,
    so task CRUD keeps working even when this returns False.

    Reads ``DBGPT_CHAT_TASK_SCHEDULER_ENABLED``. Accepts ``1/true/yes/on``
    (case-insensitive) as enabled. Unset defaults to enabled.

    Returns:
        bool: True if scheduled-task execution should run on this process.
    """
    raw = os.getenv(_SCHEDULER_ENABLED_ENV)
    if raw is None:
        return True
    return raw.strip().lower() in ("1", "true", "yes", "on")


class ScheduledTaskServe(BaseServe):
    """Serve component for scheduled tasks.

    Lifecycle:
        init_app   - include router, build service/runner/scheduler, init endpoints
        on_init    - import Entity classes to register SQLAlchemy metadata
        before_start       - create/get DB manager (sync)
        async_after_start  - start AsyncIOScheduler + recover jobs from DB
        async_before_stop  - shutdown scheduler
    """

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = "/api/v2/serve/scheduled-tasks",
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if api_tags is None:
            api_tags = [SERVE_APP_NAME_HUMP]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )
        self._config = config
        self._scheduler: Optional[TaskScheduler] = None
        self._service: Optional[ScheduledTaskService] = None

    def init_app(self, system_app: SystemApp):
        """Mount router and build service components."""
        if self._app_has_initiated:
            return
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )

        self._config = self._config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )

        # Build scheduler / service.  The runner callable is the
        # module-level run_scheduled_task (not a bound method) so that
        # APScheduler can pickle the job state if ever needed.
        #
        # Use an in-memory jobstore: the business tables are the single source
        # of truth and jobs are rehydrated on boot (_recover_jobs_from_db),
        # so there is no need for APScheduler to persist its own job table
        # (avoids a stray scheduler.db / apscheduler_jobs table in prod DBs).
        self._scheduler = TaskScheduler(jobstore_url=_IN_MEMORY_JOBSTORE_URL)
        self._service = ScheduledTaskService(
            scheduler=self._scheduler,
            runner_callable=run_scheduled_task,
        )

        init_endpoints(self._system_app, self._service)
        self._app_has_initiated = True

    def on_init(self):
        """Import Entity classes to register SQLAlchemy metadata."""
        from .models.scheduled_run_model import ScheduledRunEntity  # noqa: F401
        from .models.scheduled_task_model import ScheduledTaskEntity  # noqa: F401

    def before_start(self):
        """Create or get the database manager (sync)."""
        self.create_or_get_db_manager()

    async def async_after_start(self):
        """Start the scheduler and recover jobs from DB.

        This hook runs inside the ASGI startup event where the asyncio
        event loop is already running — the correct context for
        AsyncIOScheduler.start(). The runner auth secret is resolved in
        init_app, so the scheduler always starts here.

        Gated by DBGPT_CHAT_TASK_SCHEDULER_ENABLED: when disabled, the
        scheduler is neither started nor rehydrated, but the REST API
        (mounted in init_app) stays fully available.
        """
        if not _scheduler_enabled():
            logger.info(
                "Scheduler execution disabled via %s; REST API stays "
                "available, no jobs will be rehydrated or triggered.",
                _SCHEDULER_ENABLED_ENV,
            )
            return

        if self._scheduler is None:
            logger.warning("Scheduler not initialised; skipping startup.")
            return

        try:
            await self._scheduler.start()
            logger.info("TaskScheduler started in async_after_start.")
        except Exception:
            logger.exception("Failed to start TaskScheduler")
            return

        await self._recover_jobs_from_db()

    async def async_before_stop(self):
        """Shutdown the scheduler gracefully."""
        if self._scheduler is not None and self._scheduler.is_running():
            try:
                await self._scheduler.shutdown()
                logger.info("TaskScheduler shut down.")
            except Exception:
                logger.exception("Error shutting down TaskScheduler")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _recover_jobs_from_db(self) -> None:
        """Recover enabled tasks from DB and clean orphan scheduler jobs.

        Runs inside async_after_start (event loop is active). Uses the
        TaskScheduler public async API rather than reaching into the
        internal APScheduler instance.
        """
        if self._scheduler is None or self._service is None:
            return

        try:
            tasks = self._service._task_dao.list_enabled()
            db_task_ids: set = set()

            for t in tasks:
                task_id = t["task_id"]
                db_task_ids.add(task_id)
                cron_expr = t["cron_expression"]
                try:
                    # Idempotent re-add: remove existing then add fresh.
                    try:
                        await self._scheduler.remove_job(task_id)
                    except ValueError:
                        pass
                    await self._scheduler.add_job(
                        job_id=task_id,
                        cron_expression=cron_expr,
                        func=run_scheduled_task,
                        kwargs={"task_id": task_id},
                    )
                except Exception:
                    logger.exception("Failed to recover job %s", task_id)

            # Clean orphan jobs (in scheduler but not in DB)
            for job_info in self._scheduler.list_jobs():
                jid = job_info["job_id"]
                if jid not in db_task_ids:
                    try:
                        await self._scheduler.remove_job(jid)
                        logger.info("Removed orphan scheduler job %s", jid)
                    except Exception:
                        logger.warning("Failed to remove orphan job %s", jid)

            logger.info("Recovered %d scheduled jobs from DB", len(db_task_ids))
        except Exception:
            logger.exception("Job recovery failed")
