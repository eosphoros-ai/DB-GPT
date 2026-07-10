"""ScheduledTaskDao — CRUD + list_enabled for ScheduledTaskEntity."""

from typing import Any, Dict, List, Union

from dbgpt.storage.metadata import BaseDao

from ..models.scheduled_task_model import ScheduledTaskEntity


class ScheduledTaskDao(BaseDao[ScheduledTaskEntity, Dict[str, Any], Dict[str, Any]]):
    """DAO for ScheduledTaskEntity.

    Provides standard CRUD via BaseDao plus ``list_enabled()``
    for scheduler bootstrap.
    """

    def from_request(self, request: Union[Dict[str, Any], Any]) -> ScheduledTaskEntity:
        """Convert a request dict (or object) to a ScheduledTaskEntity.

        Args:
            request: A dict or object with task fields.

        Returns:
            ScheduledTaskEntity: The entity instance.
        """
        request_dict = request if isinstance(request, dict) else request.dict()
        entity = ScheduledTaskEntity(**request_dict)
        return entity

    def to_request(self, entity: ScheduledTaskEntity) -> Dict[str, Any]:
        """Convert a ScheduledTaskEntity to a query-ready dict.

        Only includes identity / filterable fields used by
        ``_create_query_object`` for lookups.

        Args:
            entity: The entity instance.

        Returns:
            Dict[str, Any]: The request dict.
        """
        return {
            "task_id": entity.task_id,
            "task_name": entity.task_name,
            "task_type": entity.task_type,
            "enabled": entity.enabled,
            "user_name": entity.user_name,
            "sys_code": entity.sys_code,
        }

    def to_response(self, entity: ScheduledTaskEntity) -> Dict[str, Any]:
        """Convert a ScheduledTaskEntity to a response dict.

        Args:
            entity: The entity instance.

        Returns:
            Dict[str, Any]: The full response dict with all fields.
        """
        created_at = (
            entity.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if entity.created_at
            else None
        )
        updated_at = (
            entity.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            if entity.updated_at
            else None
        )
        return {
            "id": entity.id,
            "task_id": entity.task_id,
            "task_name": entity.task_name,
            "description": entity.description,
            "task_type": entity.task_type,
            "cron_expression": entity.cron_expression,
            "payload_json": entity.payload_json,
            "enabled": entity.enabled,
            "created_at": created_at,
            "updated_at": updated_at,
            "user_name": entity.user_name,
            "sys_code": entity.sys_code,
        }

    def list_enabled(self) -> List[Dict[str, Any]]:
        """Return all tasks where enabled=True.

        Returns:
            List[Dict[str, Any]]: Response dicts for enabled tasks.
        """
        return self.get_list({"enabled": True})
