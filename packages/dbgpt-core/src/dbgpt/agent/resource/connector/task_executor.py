"""Scheduled task execution engine for connector tools."""

import asyncio
import dataclasses
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .manager import ConnectorManager


@dataclasses.dataclass
class TaskExecutionResult:
    success: bool
    result_summary: str
    error_message: Optional[str] = None
    execution_time_ms: int = 0
    timestamp: datetime = dataclasses.field(default_factory=datetime.now)


_AUTO_AUTHORIZED: Set[str] = set()


def auto_authorize(context_id: str) -> None:
    _AUTO_AUTHORIZED.add(context_id)


def revoke_authorization(context_id: str) -> None:
    _AUTO_AUTHORIZED.discard(context_id)


def is_auto_authorized(context_id: str) -> bool:
    return context_id in _AUTO_AUTHORIZED


class ConnectorTaskExecutor:
    def __init__(
        self,
        connector_manager: "ConnectorManager",
    ) -> None:
        self._manager = connector_manager

    async def execute_scheduled_task(
        self,
        task_id: str,
        connector_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> TaskExecutionResult:
        start = time.monotonic()
        auto_authorize(task_id)
        try:
            pack = self._manager.get_connector_tools(connector_id)
            if pack is None:
                return TaskExecutionResult(
                    success=False,
                    result_summary="",
                    error_message=f"Connector '{connector_id}' not found or not active",
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                )
            tool = None
            for t in pack.get_tools():
                if t.name == tool_name:
                    tool = t
                    break
            if tool is None:
                return TaskExecutionResult(
                    success=False,
                    result_summary="",
                    error_message=f"Tool '{tool_name}' not found in connector '{connector_id}'",
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                )
            result = await asyncio.wait_for(
                tool.async_execute(**tool_args),
                timeout=300,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return TaskExecutionResult(
                success=True,
                result_summary=str(result)[:500],
                execution_time_ms=elapsed,
            )
        except asyncio.TimeoutError:
            elapsed = int((time.monotonic() - start) * 1000)
            return TaskExecutionResult(
                success=False,
                result_summary="",
                error_message="Task execution timed out after 300 seconds",
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.exception("Scheduled task '%s' failed: %s", task_id, exc)
            return TaskExecutionResult(
                success=False,
                result_summary="",
                error_message=str(exc),
                execution_time_ms=elapsed,
            )
        finally:
            revoke_authorization(task_id)
