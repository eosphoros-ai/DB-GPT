import json
from typing import Type

from sqlalchemy.orm import Session

from dbgpt.core.interface.file import FileMetadata, FileMetadataIdentifier
from dbgpt.core.interface.storage import StorageItemAdapter

from .models import ServeEntity


class FileMetadataAdapter(StorageItemAdapter[FileMetadata, ServeEntity]):
    """File metadata adapter.

    Convert between storage format and database model.
    """

    def to_storage_format(self, item: FileMetadata) -> ServeEntity:
        """Convert to storage format."""
        custom_metadata = (
            {k: v for k, v in item.custom_metadata.items()}
            if item.custom_metadata
            else {}
        )
        user_name = item.user_name or custom_metadata.get("user_name")
        sys_code = item.sys_code or custom_metadata.get("sys_code")
        if "user_name" in custom_metadata:
            del custom_metadata["user_name"]
        if "sys_code" in custom_metadata:
            del custom_metadata["sys_code"]
        custom_metadata_json = (
            json.dumps(custom_metadata, ensure_ascii=False) if custom_metadata else None
        )
        return ServeEntity(
            bucket=item.bucket,
            file_id=item.file_id,
            file_name=item.file_name,
            file_size=item.file_size,
            storage_type=item.storage_type,
            storage_path=item.storage_path,
            uri=item.uri,
            custom_metadata=custom_metadata_json,
            file_hash=item.file_hash,
            user_name=user_name,
            sys_code=sys_code,
        )

    def from_storage_format(self, model: ServeEntity) -> FileMetadata:
        """Convert from storage format."""
        custom_metadata = (
            json.loads(model.custom_metadata) if model.custom_metadata else None
        )
        if custom_metadata is None:
            custom_metadata = {}
        if model.user_name:
            custom_metadata["user_name"] = model.user_name
        if model.sys_code:
            custom_metadata["sys_code"] = model.sys_code

        return FileMetadata(
            bucket=model.bucket,
            file_id=model.file_id,
            file_name=model.file_name,
            file_size=model.file_size,
            storage_type=model.storage_type,
            storage_path=model.storage_path,
            uri=model.uri,
            custom_metadata=custom_metadata,
            file_hash=model.file_hash,
            user_name=model.user_name,
            sys_code=model.sys_code,
        )

    def get_query_for_identifier(
        self,
        storage_format: Type[ServeEntity],
        resource_id: FileMetadataIdentifier,
        **kwargs,
    ):
        """Get query for identifier."""
        session: Session = kwargs.get("session")
        if session is None:
            raise Exception("session is None")
        return (
            session.query(storage_format)
            .filter(storage_format.bucket == resource_id.bucket)
            .filter(storage_format.file_id == resource_id.file_id)
        )
