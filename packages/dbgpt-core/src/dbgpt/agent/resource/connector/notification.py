"""Post-execution notification manager for scheduled connector tasks."""

import dataclasses
import logging
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from .task_executor import TaskExecutionResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .manager import ConnectorManager


@dataclasses.dataclass
class NotificationRecord:
    task_id: str
    timestamp: datetime
    status: str
    message: str
    channel: str


_notification_history: List[NotificationRecord] = []


class TaskNotificationManager:
    def __init__(self, connector_manager: Optional["ConnectorManager"] = None) -> None:
        self._manager = connector_manager

    async def notify_execution_result(
        self,
        task_id: str,
        task_name: str,
        result: TaskExecutionResult,
    ) -> None:
        status = "success" if result.success else "failed"
        if result.success:
            message = (
                f"[定时任务] {task_name} 执行成功\n"
                f"耗时: {result.execution_time_ms}ms\n"
                f"结果: {result.result_summary}"
            )
        else:
            message = f"[定时任务] {task_name} 执行失败\n错误: {result.error_message}"
        channel = "log"
        logger.info("Task notification [%s]: %s", task_id, message)
        _notification_history.append(
            NotificationRecord(
                task_id=task_id,
                timestamp=datetime.now(),
                status=status,
                message=message,
                channel=channel,
            )
        )

    async def notify_rollback(
        self,
        task_id: str,
        task_name: str,
        rollback_result: str,
    ) -> None:
        message = f"[定时任务回滚] {task_name}: {rollback_result}"
        logger.info("Rollback notification [%s]: %s", task_id, message)
        _notification_history.append(
            NotificationRecord(
                task_id=task_id,
                timestamp=datetime.now(),
                status="rollback",
                message=message,
                channel="log",
            )
        )

    def get_notification_history(self, task_id: str) -> List[NotificationRecord]:
        return [r for r in _notification_history if r.task_id == task_id]
