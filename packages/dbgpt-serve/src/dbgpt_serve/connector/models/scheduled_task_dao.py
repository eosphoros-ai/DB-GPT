"""DAO for scheduled connector tasks."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from dbgpt.storage.metadata import BaseDao

from .scheduled_task_model import ScheduledTaskEntity

logger = logging.getLogger(__name__)


class ScheduledTaskDao(BaseDao[ScheduledTaskEntity, Dict[str, Any], Dict[str, Any]]):
    """DAO for ScheduledTaskEntity providing CRUD operations."""

    def from_request(self, request: Union[Dict[str, Any], Any]) -> ScheduledTaskEntity:
        request_dict = request if isinstance(request, dict) else request.dict()
        return ScheduledTaskEntity(**request_dict)

    def to_request(self, entity: ScheduledTaskEntity) -> Dict[str, Any]:
        return {
            "task_id": entity.task_id,
            "connector_id": entity.connector_id,
            "task_name": entity.task_name,
            "description": entity.description,
            "cron_expression": entity.cron_expression,
            "tool_name": entity.tool_name,
            "tool_args": entity.tool_args,
            "enabled": entity.enabled,
            "user_name": entity.user_name,
            "sys_code": entity.sys_code,
        }

    def to_response(self, entity: ScheduledTaskEntity) -> Dict[str, Any]:
        return {
            "id": entity.id,
            "task_id": entity.task_id,
            "connector_id": entity.connector_id,
            "task_name": entity.task_name,
            "description": entity.description,
            "cron_expression": entity.cron_expression,
            "tool_name": entity.tool_name,
            "tool_args": entity.tool_args,
            "enabled": entity.enabled,
            "last_run_time": entity.last_run_time.strftime("%Y-%m-%d %H:%M:%S")
            if entity.last_run_time
            else None,
            "last_run_status": entity.last_run_status,
            "last_run_result": entity.last_run_result,
            "created_at": entity.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if entity.created_at
            else None,
            "updated_at": entity.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            if entity.updated_at
            else None,
            "user_name": entity.user_name,
            "sys_code": entity.sys_code,
        }

    def get_by_task_id(self, task_id: str) -> Optional[ScheduledTaskEntity]:
        with self.session() as session:
            return (
                session.query(ScheduledTaskEntity)
                .filter(ScheduledTaskEntity.task_id == task_id)
                .first()
            )

    def list_by_connector(self, connector_id: str) -> List[ScheduledTaskEntity]:
        with self.session() as session:
            return (
                session.query(ScheduledTaskEntity)
                .filter(ScheduledTaskEntity.connector_id == connector_id)
                .all()
            )

    def list_enabled(self) -> List[ScheduledTaskEntity]:
        with self.session() as session:
            return (
                session.query(ScheduledTaskEntity)
                .filter(
                    ScheduledTaskEntity.enabled == True  # noqa: E712
                )
                .all()
            )

    def update_last_run(self, task_id: str, status: str, result: str) -> None:
        with self.session() as session:
            entity = (
                session.query(ScheduledTaskEntity)
                .filter(ScheduledTaskEntity.task_id == task_id)
                .first()
            )
            if entity:
                entity.last_run_time = datetime.now()
                entity.last_run_status = status
                entity.last_run_result = result
                entity.updated_at = datetime.now()
