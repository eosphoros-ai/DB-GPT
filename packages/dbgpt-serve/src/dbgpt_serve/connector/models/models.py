import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt.storage.metadata import BaseDao, Model

from ..config import ServeConfig

logger = logging.getLogger(__name__)


class ConnectorInstanceEntity(Model):
    __tablename__ = "connector_instance"

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="Auto increment id"
    )
    connector_id = Column(
        String(64), unique=True, nullable=False, comment="Connector UUID"
    )
    connector_type = Column(
        String(64), nullable=False, comment="Connector type, e.g. yuque, feishu"
    )
    display_name = Column(String(256), nullable=True, comment="Display name")
    encrypted_credentials = Column(
        Text, nullable=True, comment="Encrypted credentials JSON"
    )
    encryption_salt = Column(String(256), nullable=True, comment="Encryption salt")
    status = Column(
        String(32),
        nullable=True,
        comment="Status: active/error/disconnected/needs_reactivation",
    )
    config_json = Column(Text, nullable=True, comment="Optional extra config JSON")
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )

    def __repr__(self):
        return (
            f"ConnectorInstanceEntity(id={self.id}, "
            f"connector_id='{self.connector_id}', "
            f"connector_type='{self.connector_type}', "
            f"display_name='{self.display_name}', "
            f"status='{self.status}', user_name='{self.user_name}')"
        )


class ConnectorInstanceDao(
    BaseDao[ConnectorInstanceEntity, Dict[str, Any], Dict[str, Any]]
):
    """DAO for ConnectorInstanceEntity providing basic CRUD operations."""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(
        self, request: Union[Dict[str, Any], Any]
    ) -> ConnectorInstanceEntity:
        """Convert a request dict to a ConnectorInstanceEntity.

        Args:
            request: Request dict or object with connector fields.

        Returns:
            ConnectorInstanceEntity: The entity instance.
        """
        request_dict = request if isinstance(request, dict) else request.dict()
        entity = ConnectorInstanceEntity(**request_dict)
        if not entity.connector_id:
            entity.connector_id = str(uuid.uuid4())
        return entity

    def to_request(self, entity: ConnectorInstanceEntity) -> Dict[str, Any]:
        """Convert a ConnectorInstanceEntity to a request dict.

        Args:
            entity: The entity instance.

        Returns:
            Dict[str, Any]: The request dict.
        """
        return {
            "connector_id": entity.connector_id,
            "connector_type": entity.connector_type,
            "display_name": entity.display_name,
            "encrypted_credentials": entity.encrypted_credentials,
            "encryption_salt": entity.encryption_salt,
            "status": entity.status,
            "config_json": entity.config_json,
            "user_name": entity.user_name,
            "sys_code": entity.sys_code,
        }

    def to_response(self, entity: ConnectorInstanceEntity) -> Dict[str, Any]:
        """Convert a ConnectorInstanceEntity to a response dict.

        Args:
            entity: The entity instance.

        Returns:
            Dict[str, Any]: The response dict.
        """
        gmt_created_str = (
            entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_created
            else None
        )
        gmt_modified_str = (
            entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
            if entity.gmt_modified
            else None
        )
        return {
            "id": entity.id,
            "connector_id": entity.connector_id,
            "connector_type": entity.connector_type,
            "display_name": entity.display_name,
            "status": entity.status,
            "config_json": entity.config_json,
            "user_name": entity.user_name,
            "sys_code": entity.sys_code,
            "gmt_created": gmt_created_str,
            "gmt_modified": gmt_modified_str,
        }
