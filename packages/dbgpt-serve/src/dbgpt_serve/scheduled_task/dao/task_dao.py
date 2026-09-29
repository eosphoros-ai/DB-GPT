"""ScheduledTaskDao — CRUD + list_enabled for ScheduledTaskEntity."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import or_

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
            "owner_id": entity.owner_id,
            "sys_code": entity.sys_code,
            "resource_type": entity.resource_type,
            "resource_id": entity.resource_id,
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
            "owner_id": entity.owner_id,
            "sys_code": entity.sys_code,
            "resource_type": entity.resource_type,
            "resource_id": entity.resource_id,
            "lease_owner": entity.lease_owner,
            "lease_expires_at": entity.lease_expires_at,
        }

    def list_enabled(self) -> List[Dict[str, Any]]:
        """Return all tasks where enabled=True.

        Returns:
            List[Dict[str, Any]]: Response dicts for enabled tasks.
        """
        return self.get_list({"enabled": True})

    def list_owned(
        self,
        owner_id: str,
        *,
        task_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"owner_id": owner_id}
        if task_type:
            query["task_type"] = task_type
        if resource_type:
            query["resource_type"] = resource_type
        if resource_id:
            query["resource_id"] = resource_id
        if enabled_only:
            query["enabled"] = True
        return self.get_list(query)

    def get_owned(self, task_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        return self.get_one({"task_id": task_id, "owner_id": owner_id})

    def try_acquire_lease(
        self,
        task_id: str,
        lease_owner: str,
        *,
        ttl_seconds: int,
        require_enabled: bool = True,
    ) -> bool:
        now = datetime.now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self.session() as session:
            conditions = [
                ScheduledTaskEntity.task_id == task_id,
                or_(
                    ScheduledTaskEntity.lease_expires_at.is_(None),
                    ScheduledTaskEntity.lease_expires_at < now,
                ),
            ]
            if require_enabled:
                conditions.append(ScheduledTaskEntity.enabled.is_(True))
            count = (
                session.query(ScheduledTaskEntity)
                .filter(*conditions)
                .update(
                    {
                        ScheduledTaskEntity.lease_owner: lease_owner,
                        ScheduledTaskEntity.lease_expires_at: expires_at,
                    },
                    synchronize_session=False,
                )
            )
            return count == 1

    def release_lease(self, task_id: str, lease_owner: str) -> None:
        with self.session() as session:
            (
                session.query(ScheduledTaskEntity)
                .filter(
                    ScheduledTaskEntity.task_id == task_id,
                    ScheduledTaskEntity.lease_owner == lease_owner,
                )
                .update(
                    {
                        ScheduledTaskEntity.lease_owner: None,
                        ScheduledTaskEntity.lease_expires_at: None,
                    },
                    synchronize_session=False,
                )
            )
