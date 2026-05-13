"""Connector scheduler module using APScheduler."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

from dbgpt.component import BaseComponent, SystemApp


class ConnectorScheduler(BaseComponent):
    """APScheduler-based scheduler for connector tasks."""

    name = "connector_scheduler"

    def __init__(self, system_app: Optional[SystemApp] = None):
        super().__init__(system_app)
        self._scheduler: Optional[Any] = None
        self._job_store_url: str = "sqlite:///connector_jobs.db"

    def init_app(self, system_app: SystemApp) -> None:
        self._system_app = system_app
        # Try to get DB URL from system_app config
        try:
            cfg = system_app.config
            if hasattr(cfg, "LOCAL_DB_PATH"):
                self._job_store_url = f"sqlite:///{cfg.LOCAL_DB_PATH}/connector_jobs.db"
        except Exception:
            pass

    def _get_scheduler(self) -> Any:
        if not HAS_APSCHEDULER:
            raise ImportError(
                "apscheduler is required. Install with: pip install apscheduler>=3.10,<4"
            )
        if self._scheduler is None:
            jobstores = {"default": SQLAlchemyJobStore(url=self._job_store_url)}
            self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        return self._scheduler

    async def start(self) -> None:
        scheduler = self._get_scheduler()
        if not scheduler.running:
            scheduler.start()
            logger.info("ConnectorScheduler started")

    async def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("ConnectorScheduler shutdown")

    def add_job(
        self,
        connector_id: str,
        task_name: str,
        cron_expr: str,
        func: Any,
        kwargs: Optional[Dict] = None,
    ) -> str:
        """Add a cron job. Returns job_id."""
        scheduler = self._get_scheduler()
        job_id = f"connector:{connector_id}:{task_name}"
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs or {},
            replace_existing=True,
        )
        logger.info(f"Added job {job_id}")
        return job_id

    def remove_job(self, job_id: str) -> None:
        scheduler = self._get_scheduler()
        try:
            scheduler.remove_job(job_id)
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")

    def remove_connector_jobs(self, connector_id: str) -> None:
        """Remove all jobs for a connector."""
        scheduler = self._get_scheduler()
        prefix = f"connector:{connector_id}:"
        for job in scheduler.get_jobs():
            if job.id.startswith(prefix):
                job.remove()
                logger.info(f"Removed job {job.id}")

    def list_jobs(self, connector_id: Optional[str] = None) -> List[Dict]:
        scheduler = self._get_scheduler()
        jobs = scheduler.get_jobs()
        result = []
        for job in jobs:
            if connector_id and not job.id.startswith(f"connector:{connector_id}:"):
                continue
            result.append(
                {
                    "job_id": job.id,
                    "next_run_time": str(job.next_run_time)
                    if job.next_run_time
                    else None,
                    "name": job.name,
                }
            )
        return result

    def pause_job(self, job_id: str) -> None:
        self._get_scheduler().pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        self._get_scheduler().resume_job(job_id)
