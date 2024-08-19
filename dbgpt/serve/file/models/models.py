"""This is an auto-generated model file
You can define your own models and DAOs here
"""

from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model, db

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class ServeEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    __table_args__ = (UniqueConstraint("bucket", "file_id", name="uk_bucket_file_id"),)

    id = Column(Integer, primary_key=True, comment="Auto increment id")

    bucket = Column(String(255), nullable=False, comment="Bucket name")
    file_id = Column(String(255), nullable=False, comment="File id")
    file_name = Column(String(256), nullable=False, comment="File name")
    file_size = Column(Integer, nullable=True, comment="File size")
    storage_type = Column(String(32), nullable=False, comment="Storage type")
    storage_path = Column(String(512), nullable=False, comment="Storage path")
    uri = Column(String(512), nullable=False, comment="File URI")
    custom_metadata = Column(
        Text, nullable=True, comment="Custom metadata, JSON format"
    )
    file_hash = Column(String(128), nullable=True, comment="File hash")
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")

    def __repr__(self):
        return (
            f"ServeEntity(id={self.id}, gmt_created='{self.gmt_created}', "
            f"gmt_modified='{self.gmt_modified}')"
        )


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for File"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(self, request: Union[ServeRequest, Dict[str, Any]]) -> ServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.to_dict() if isinstance(request, ServeRequest) else request
        )
        entity = ServeEntity(**request_dict)
        # TODO implement your own logic here, transfer the request_dict to an entity
        return entity

    def to_request(self, entity: ServeEntity) -> ServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        # TODO implement your own logic here, transfer the entity to a request
        return ServeRequest()

    def to_response(self, entity: ServeEntity) -> ServerResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        # TODO implement your own logic here, transfer the entity to a response
        return ServerResponse()
