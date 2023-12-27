"""This is an auto-generated model file
You can define your own models and DAOs here
"""
from typing import Union, Any, Dict
from datetime import datetime
from sqlalchemy import Column, Integer, String, Index, Text, DateTime
from dbgpt.storage.metadata import Model, BaseDao, db
from ..api.schemas import ServeRequest, ServerResponse
from ..config import ServeConfig, SERVER_APP_TABLE_NAME


class ServeEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="Auto increment id")

    # TODO: define your own fields here

    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")

    def __repr__(self):
        return f"ServeEntity(id={self.id}, gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for Conversation"""

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
        request_dict = request.dict() if isinstance(request, ServeRequest) else request
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
