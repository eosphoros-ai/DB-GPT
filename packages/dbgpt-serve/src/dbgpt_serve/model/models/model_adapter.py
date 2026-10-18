import json
from typing import Type

from sqlalchemy.orm import Session

from dbgpt.core.interface.storage import StorageItemAdapter
from dbgpt.model.cluster.storage import (
    ModelProviderConfigIdentifier,
    ModelProviderConfigItem,
    ModelStorageIdentifier,
    ModelStorageItem,
)

from .models import ModelProviderConfigEntity, ServeEntity


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


class ModelProviderConfigAdapter(
    StorageItemAdapter[ModelProviderConfigItem, ModelProviderConfigEntity]
):
    """Adapter between provider config storage item and database entity."""

    def to_storage_format(
        self, item: ModelProviderConfigItem
    ) -> ModelProviderConfigEntity:
        return ModelProviderConfigEntity(
            provider=item.provider,
            label=item.label,
            api_key=item.api_key,
            api_base=item.api_base,
            enabled_models=json.dumps(item.enabled_models, ensure_ascii=False),
        )

    def from_storage_format(
        self, entity: ModelProviderConfigEntity
    ) -> ModelProviderConfigItem:
        return ModelProviderConfigItem(
            provider=entity.provider,
            label=entity.label,
            api_key=entity.api_key,
            api_base=entity.api_base,
            enabled_models=json.loads(entity.enabled_models)
            if entity.enabled_models
            else [],
        )

    def get_query_for_identifier(
        self,
        storage_format: Type[ModelProviderConfigEntity],
        resource_id: ModelProviderConfigIdentifier,
        **kwargs,
    ):
        session: Session = kwargs.get("session")
        if session is None:
            raise Exception("session is None")
        return session.query(storage_format).filter(
            storage_format.provider == resource_id.provider
        )
