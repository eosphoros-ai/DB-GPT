import json
from typing import Type

from sqlalchemy.orm import Session

from dbgpt.core.interface.storage import StorageItemAdapter
from dbgpt.model.cluster.storage import ModelStorageIdentifier, ModelStorageItem

from .models import ServeEntity


class ModelStorageAdapter(StorageItemAdapter[ModelStorageItem, ServeEntity]):
    """File metadata adapter.

    Convert between storage format and database model.
    """

    def to_storage_format(self, item: ModelStorageItem) -> ServeEntity:
        """Convert to storage format."""
        params = json.dumps(item.params, ensure_ascii=False)
        enabled = 1 if item.enabled else 0
        return ServeEntity(
            host=item.host,
            port=item.port,
            model=item.model,
            provider=item.provider,
            worker_type=item.worker_type,
            enabled=enabled,
            worker_name=item.worker_name,
            params=params,
            description=item.description,
            user_name=item.user_name,
            sys_code=item.sys_code,
        )

    def from_storage_format(self, model: ServeEntity) -> ModelStorageItem:
        """Convert from storage format."""
        params = json.loads(model.params)
        enabled = True if model.enabled else False
        return ModelStorageItem(
            host=model.host,
            port=model.port,
            model=model.model,
            provider=model.provider,
            worker_type=model.worker_type,
            enabled=enabled,
            worker_name=model.worker_name,
            params=params,
            description=model.description,
            user_name=model.user_name,
            sys_code=model.sys_code,
        )

    def get_query_for_identifier(
        self,
        storage_format: Type[ServeEntity],
        resource_id: ModelStorageIdentifier,
        **kwargs,
    ):
        """Get query for identifier."""
        session: Session = kwargs.get("session")
        if session is None:
            raise Exception("session is None")
        query = (
            session.query(storage_format)
            .filter(storage_format.model == resource_id.model)
            .filter(storage_format.worker_type == resource_id.worker_type)
        )
        if resource_id.user_name:
            query = query.filter(storage_format.user_name == resource_id.user_name)
        if resource_id.sys_code:
            query = query.filter(storage_format.sys_code == resource_id.sys_code)
        return query
