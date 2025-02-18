"""This is an auto-generated model file
You can define your own models and DAOs here
"""

from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class ServeEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    __table_args__ = (
        UniqueConstraint(
            "model", "provider", "worker_type", name="uk_model_provider_type"
        ),
    )
    id = Column(Integer, primary_key=True, comment="Auto increment id")

    host = Column(String(255), nullable=False, comment="The model worker host")
    port = Column(Integer, nullable=False, comment="The model worker port")
    model = Column(String(255), nullable=False, comment="The model name")
    provider = Column(String(255), nullable=False, comment="The model provider")
    worker_type = Column(String(255), nullable=False, comment="The worker type")
    params = Column(Text, nullable=False, comment="The model parameters, JSON format")
    enabled = Column(
        Integer,
        default=1,
        nullable=True,
        comment="Whether the model is enabled, if it is enabled, it will be started "
        "when the system starts, 1 is enabled, 0 is disabled",
    )
    worker_name = Column(String(255), nullable=True, comment="The worker name")
    description = Column(Text, nullable=True, comment="The model description")
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
    """The DAO class for Model"""

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
