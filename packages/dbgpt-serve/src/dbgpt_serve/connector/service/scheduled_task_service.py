"""Service layer for scheduled connector tasks."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _validate_cron(cron_expression: str) -> None:
    try:
        from apscheduler.triggers.cron import CronTrigger

        CronTrigger.from_crontab(cron_expression)
    except Exception as e:
        raise ValueError(f"Invalid cron expression '{cron_expression}': {e}")


class ScheduledTaskService:
    """Business logic for scheduled connector tasks."""

    def __init__(self) -> None:
        from .scheduled_task_dao import ScheduledTaskDao

        self._dao = ScheduledTaskDao()

    def create_task(self, request: Dict[str, Any]) -> Dict[str, Any]:
        cron_expression = request.get("cron_expression", "")
        _validate_cron(cron_expression)

        task_id = str(uuid.uuid4())
        entity_data = {
            "task_id": task_id,
            "connector_id": request["connector_id"],
            "task_name": request["task_name"],
            "description": request.get("description"),
            "cron_expression": cron_expression,
            "tool_name": request["tool_name"],
            "tool_args": json.dumps(request.get("tool_args", {})),
            "enabled": request.get("enabled", True),
            "user_name": request.get("user_name"),
            "sys_code": request.get("sys_code"),
        }
        entity = self._dao.from_request(entity_data)
        saved = self._dao.save(entity)
        return self._dao.to_response(saved)

    def list_tasks(self, connector_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if connector_id:
            entities = self._dao.list_by_connector(connector_id)
        else:
            with self._dao.session() as session:
                from .scheduled_task_model import ScheduledTaskEntity

                entities = session.query(ScheduledTaskEntity).all()
        return [self._dao.to_response(e) for e in entities]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        entity = self._dao.get_by_task_id(task_id)
        return self._dao.to_response(entity) if entity else None

    def update_task(self, task_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        entity = self._dao.get_by_task_id(task_id)
        if entity is None:
            raise ValueError(f"Task '{task_id}' not found")
        if "cron_expression" in request:
            _validate_cron(request["cron_expression"])
            entity.cron_expression = request["cron_expression"]
        if "task_name" in request:
            entity.task_name = request["task_name"]
        if "description" in request:
            entity.description = request["description"]
        if "tool_name" in request:
            entity.tool_name = request["tool_name"]
        if "tool_args" in request:
            entity.tool_args = json.dumps(request["tool_args"])
        if "enabled" in request:
            entity.enabled = request["enabled"]
        updated = self._dao.update(entity)
        return self._dao.to_response(updated)

    def delete_task(self, task_id: str) -> None:
        entity = self._dao.get_by_task_id(task_id)
        if entity is None:
            raise ValueError(f"Task '{task_id}' not found")
        self._dao.delete(entity.id)

    def toggle_task(self, task_id: str, enabled: bool) -> Dict[str, Any]:
        return self.update_task(task_id, {"enabled": enabled})
