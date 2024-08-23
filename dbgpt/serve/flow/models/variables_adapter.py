from typing import Type

from sqlalchemy.orm import Session

from dbgpt.core.interface.storage import StorageItemAdapter
from dbgpt.core.interface.variables import StorageVariables, VariablesIdentifier

from .models import VariablesEntity


class VariablesAdapter(StorageItemAdapter[StorageVariables, VariablesEntity]):
    """Variables adapter.

    Convert between storage format and database model.
    """

    def to_storage_format(self, item: StorageVariables) -> VariablesEntity:
        """Convert to storage format."""
        return VariablesEntity(
            key=item.key,
            name=item.name,
            label=item.label,
            value=item.value,
            value_type=item.value_type,
            category=item.category,
            encryption_method=item.encryption_method,
            salt=item.salt,
            scope=item.scope,
            scope_key=item.scope_key,
            sys_code=item.sys_code,
            user_name=item.user_name,
            description=item.description,
        )

    def from_storage_format(self, model: VariablesEntity) -> StorageVariables:
        """Convert from storage format."""
        return StorageVariables(
            key=model.key,
            name=model.name,
            label=model.label,
            value=model.value,
            value_type=model.value_type,
            category=model.category,
            encryption_method=model.encryption_method,
            salt=model.salt,
            scope=model.scope,
            scope_key=model.scope_key,
            sys_code=model.sys_code,
            user_name=model.user_name,
            description=model.description,
        )

    def get_query_for_identifier(
        self,
        storage_format: Type[VariablesEntity],
        resource_id: VariablesIdentifier,
        **kwargs,
    ):
        """Get query for identifier."""
        session: Session = kwargs.get("session")
        if session is None:
            raise Exception("session is None")
        query_obj = session.query(VariablesEntity)
        for key, value in resource_id.to_dict().items():
            if value is None:
                continue
            query_obj = query_obj.filter(getattr(VariablesEntity, key) == value)

        # enabled must be True
        query_obj = query_obj.filter(VariablesEntity.enabled == 1)
        return query_obj
