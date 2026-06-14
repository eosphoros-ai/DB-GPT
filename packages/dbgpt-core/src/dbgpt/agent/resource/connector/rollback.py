"""Conservative rollback manager for scheduled connector tasks."""

import dataclasses
import logging
from datetime import datetime
from typing import Any, Dict

from .task_executor import TaskExecutionResult

logger = logging.getLogger(__name__)

_NON_ROLLBACKABLE_TOOLS = {
    "send_message",
    "send_notification",
    "send_email",
    "post_message",
    "publish",
}


@dataclasses.dataclass
class RollbackResult:
    rolled_back: bool
    message: str
    timestamp: datetime = dataclasses.field(default_factory=datetime.now)


class TaskRollbackManager:
    def is_rollbackable(self, tool_name: str, connector_type: str) -> bool:
        if tool_name in _NON_ROLLBACKABLE_TOOLS:
            return False
        return False

    async def execute_rollback(
        self,
        task_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        execution_result: TaskExecutionResult,
    ) -> RollbackResult:
        if not self.is_rollbackable(tool_name, ""):
            msg = f"Tool '{tool_name}' does not support rollback (conservative policy)"
            logger.info("Rollback skipped for task '%s': %s", task_id, msg)
            return RollbackResult(rolled_back=False, message=msg)
        return RollbackResult(rolled_back=False, message="Rollback not implemented")
