"""ScheduledRunDao — CRUD + run-history queries for ScheduledRunEntity."""

from typing import Any, Dict, List, Union

from dbgpt.storage.metadata import BaseDao

from ..models.scheduled_run_model import ScheduledRunEntity


class ScheduledRunDao(BaseDao[ScheduledRunEntity, Dict[str, Any], Dict[str, Any]]):
    """DAO for ScheduledRunEntity.

    Provides standard CRUD via BaseDao plus ``list_by_task_id()``
    for run-history queries.
    """

    def from_request(self, request: Union[Dict[str, Any], Any]) -> ScheduledRunEntity:
        """Convert a request dict (or entity) to a ScheduledRunEntity.

        Args:
            request: A dict with run fields, or an existing ScheduledRunEntity.

        Returns:
            ScheduledRunEntity: The entity instance.
        """
        if isinstance(request, ScheduledRunEntity):
            return request
        request_dict = request if isinstance(request, dict) else request.dict()
        return ScheduledRunEntity(**request_dict)

    def to_request(self, entity: ScheduledRunEntity) -> Dict[str, Any]:
        """Convert a ScheduledRunEntity to a query dict (keyed by run_id).

        Args:
            entity: The entity instance.

        Returns:
            Dict[str, Any]: A dict suitable for ``get_one`` lookup.
        """
        return {"run_id": entity.run_id}

    def to_response(self, entity: ScheduledRunEntity) -> Dict[str, Any]:
        """Convert a ScheduledRunEntity to a response dict.

        Args:
            entity: The entity instance.

        Returns:
            Dict[str, Any]: The response dict with all 9 fields.
        """
        return {
            "id": entity.id,
            "run_id": entity.run_id,
            "task_id": entity.task_id,
            "started_at": entity.started_at,
            "finished_at": entity.finished_at,
            "status": entity.status,
            "result_summary": entity.result_summary,
            "error_message": entity.error_message,
            "output_conv_uid": entity.output_conv_uid,
        }

    def list_by_task_id(
        self, task_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Return runs for a given task_id, ordered by started_at descending.

        Args:
            task_id: The task UUID to filter by.
            limit: Maximum number of results (default 50).
            offset: Number of results to skip (default 0).

        Returns:
            List[Dict[str, Any]]: Run records as response dicts, newest first.
        """
        with self.session() as session:
            results = (
                session.query(ScheduledRunEntity)
                .filter(ScheduledRunEntity.task_id == task_id)
                .order_by(ScheduledRunEntity.started_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [self.to_response(entity) for entity in results]
