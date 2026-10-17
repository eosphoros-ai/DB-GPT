"""Execution core for persistent dashboard-refresh schedules."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Callable, Optional

from ..api.schemas import DashboardRefreshPayload
from ..dao.run_dao import ScheduledRunDao
from ..dao.task_dao import ScheduledTaskDao

logger = logging.getLogger(__name__)

_ERROR_MAX = 2000
_SUMMARY_MAX = 1024


class PartialDashboardRefreshError(RuntimeError):
    """Carry a safe partial result through the bounded retry loop."""

    def __init__(self, result: dict):
        self.result = result
        failed = result.get("failed_widget_count", 0)
        super().__init__(f"{failed} dashboard widgets failed to refresh")


class DashboardRefreshRunner:
    """Refresh a dashboard, optionally publish, and persist a bounded result."""

    def __init__(
        self,
        dashboard_service_factory: Optional[Callable] = None,
        task_dao: Optional[ScheduledTaskDao] = None,
        run_dao: Optional[ScheduledRunDao] = None,
    ) -> None:
        self._dashboard_service_factory = dashboard_service_factory
        self._task_dao = task_dao or ScheduledTaskDao()
        self._run_dao = run_dao or ScheduledRunDao()

    def _dashboard_service(self):
        if self._dashboard_service_factory:
            return self._dashboard_service_factory()
        # Lazy import preserves dbgpt-serve's package boundary at import time.
        from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService

        return DashboardService()

    async def refresh_dashboard_task(
        self, task_id: str, *, allow_disabled: bool = False
    ) -> None:
        run_id = str(uuid.uuid4())
        task = self._task_dao.get_one({"task_id": task_id})
        self._run_dao.create(
            {
                "run_id": run_id,
                "task_id": task_id,
                "started_at": datetime.now(),
                "status": "running",
                "attempt_count": 0,
                "idempotency_key": run_id,
            }
        )

        if task is None:
            self._fail(run_id, "task not found", attempt_count=0)
            return
        if not task.get("enabled", False) and not allow_disabled:
            self._fail(run_id, "task disabled", attempt_count=0)
            return
        if task.get("task_type") != "dashboard_refresh":
            self._fail(run_id, "unexpected task type", attempt_count=0)
            return

        try:
            payload = DashboardRefreshPayload(
                **json.loads(task.get("payload_json") or "{}")
            )
            owner_id = task.get("owner_id") or task.get("user_name")
            if not owner_id:
                raise ValueError("dashboard schedule has no authenticated owner")

            last_error: Optional[Exception] = None
            partial_result: Optional[dict] = None
            for attempt in range(1, payload.max_attempts + 1):
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            self._run_once,
                            payload,
                            owner_id,
                        ),
                        timeout=payload.timeout_seconds,
                    )
                    result["attempt_count"] = attempt
                    self._complete(run_id, result, status="success")
                    return
                except PartialDashboardRefreshError as exc:
                    partial_result = exc.result
                    partial_result["attempt_count"] = attempt
                    last_error = exc
                except asyncio.TimeoutError:
                    last_error = TimeoutError(
                        f"execution exceeded {payload.timeout_seconds}s"
                    )
                except Exception as exc:  # errors are retried and persisted
                    last_error = exc
                if attempt < payload.max_attempts:
                    await asyncio.sleep(min(2 ** (attempt - 1), 10))

            if partial_result is not None:
                successful = partial_result.get("successful_widget_count", 0)
                status = "partial_success" if successful else "failed"
                self._complete(run_id, partial_result, status=status)
                return

            self._fail(
                run_id,
                str(last_error or "dashboard refresh failed"),
                attempt_count=payload.max_attempts,
                status="timeout" if isinstance(last_error, TimeoutError) else "failed",
            )
        except Exception as exc:
            logger.exception("dashboard schedule %s failed", task_id)
            self._fail(run_id, str(exc), attempt_count=1)

    def _run_once(self, payload: DashboardRefreshPayload, owner_id: str) -> dict:
        from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardAction

        service = self._dashboard_service()
        service.require_permission(
            payload.dashboard_id, owner_id, DashboardAction.MANAGE_SCHEDULE
        )
        snapshot = service.refresh_dashboard(
            payload.dashboard_id, payload.filters, owner_id
        )
        failed_widgets = [
            widget_id
            for widget_id, result in snapshot.widgets.items()
            if result.error is not None
        ]
        result = {
            "dashboard_id": payload.dashboard_id,
            "refreshed_at": snapshot.refreshed_at.isoformat(),
            "widget_count": len(snapshot.widgets),
            "successful_widget_count": len(snapshot.widgets) - len(failed_widgets),
            "failed_widget_count": len(failed_widgets),
            "failed_widget_ids": sorted(failed_widgets),
            "filter_keys": sorted(payload.filters.keys()),
            "published": False,
        }
        if failed_widgets:
            # Preserve successful widget results in the dashboard snapshot, but do
            # not publish an incomplete snapshot. A retry may still heal the rest.
            raise PartialDashboardRefreshError(result)

        if payload.publish_after_refresh:
            current = service.get_dashboard(payload.dashboard_id, owner_id)
            published = service.publish_dashboard(
                payload.dashboard_id,
                current.current_revision,
                payload.filters,
                owner_id,
            )
            result.update(
                {
                    "published": True,
                    "published_revision": published.published_revision,
                    "share_path": published.share_path,
                }
            )
        return result

    def _complete(self, run_id: str, result: dict, *, status: str) -> None:
        self._run_dao.update(
            {"run_id": run_id},
            {
                "status": status,
                "finished_at": datetime.now(),
                "attempt_count": result.get("attempt_count", 1),
                "result_summary": self._summary(result),
                "result_json": json.dumps(
                    result,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "output_resource_id": result.get("share_path"),
            },
        )

    def _fail(
        self,
        run_id: str,
        message: str,
        *,
        attempt_count: int,
        status: str = "failed",
    ) -> None:
        self._run_dao.update(
            {"run_id": run_id},
            {
                "status": status,
                "finished_at": datetime.now(),
                "attempt_count": attempt_count,
                "error_message": message[:_ERROR_MAX],
            },
        )

    @staticmethod
    def _summary(result: dict) -> str:
        dashboard_id = result.get("dashboard_id")
        widget_count = result.get("widget_count", 0)
        failed_count = result.get("failed_widget_count", 0)
        published = " and published" if result.get("published") else ""
        partial = f" ({failed_count} failed)" if failed_count else ""
        return (
            f"Dashboard {dashboard_id} refreshed {widget_count} widgets"
            f"{partial}{published}."
        )[:_SUMMARY_MAX]
