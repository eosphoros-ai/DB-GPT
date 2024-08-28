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
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    name = Column(String(255), unique=True, nullable=False, comment="gpts name")
    type = Column(String(255), nullable=False, comment="gpts type")
    version = Column(String(255), nullable=False, comment="gpts version")
    user_name = Column(String(255), nullable=True, comment="user name")
    file_name = Column(String(255), nullable=True, comment="gpts package file name")
    use_count = Column(
        Integer, nullable=True, default=0, comment="gpts total use count"
    )
    succ_count = Column(
        Integer, nullable=True, default=0, comment="gpts total success count"
    )
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.utcnow, comment="gpts install time")
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.utcnow,
        comment="Record update time",
    )
    UniqueConstraint("user_name", "name", name="uk_name")


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for MyDbgpts"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(self, request: Union[ServeRequest, Dict[str, Any]]) -> ServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[MyGptsServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.to_dict() if isinstance(request, ServeRequest) else request
        )
        entity = ServeEntity(**request_dict)

        return entity

    def to_request(self, entity: ServeEntity) -> ServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return ServeRequest(
            id=entity.id,
            user_name=entity.user_name,
            sys_code=entity.sys_code,
            name=entity.name,
            file_name=entity.file_name,
            type=entity.type,
            version=entity.version,
            use_count=entity.use_count,
            succ_count=entity.succ_count,
        )

    def to_response(self, entity: ServeEntity) -> ServerResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        gmt_created_str = (
            entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_created
            else ""
        )
        gmt_modified_str = (
            entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_modified
            else ""
        )
        request = self.to_request(entity)

        return ServerResponse(
            **request.to_dict(),
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )
