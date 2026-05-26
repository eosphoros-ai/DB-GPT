"""Connector service for managing external connector instances."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from dbgpt.agent.resource.connector.credential import CredentialStore
from dbgpt.agent.resource.connector.manager import ConnectorManager
from dbgpt.component import SystemApp
from dbgpt.storage.metadata import BaseDao
from dbgpt.util import get_or_create_event_loop
from dbgpt_serve.core import BaseService
from dbgpt_serve.core.config import BaseServeConfig

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ConnectorInstanceDao, ConnectorInstanceEntity

logger = logging.getLogger(__name__)


class ConnectorCreateRequest(BaseModel):
    """Request model for creating a connector."""

    connector_type: str = Field(..., description="Connector type, e.g. yuque, feishu")
    display_name: str = Field(..., description="Display name for the connector")
    credentials: Dict[str, Any] = Field(..., description="Connector credentials")
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional extra config"
    )
    user_name: Optional[str] = Field(default=None, description="User name")
    sys_code: Optional[str] = Field(default=None, description="System code")


class ConnectorUpdateRequest(BaseModel):
    """Request model for updating a connector."""

    display_name: Optional[str] = Field(
        default=None, description="Display name for the connector"
    )
    credentials: Optional[Dict[str, Any]] = Field(
        default=None, description="Connector credentials"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional extra config"
    )


class ConnectorResponse(BaseModel):
    """Response model for a connector."""

    connector_id: str = Field(..., description="Connector UUID")
    connector_type: str = Field(..., description="Connector type")
    display_name: str = Field(..., description="Display name")
    status: str = Field(..., description="Status: active/error/disconnected")
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional extra config"
    )
    user_name: Optional[str] = Field(default=None, description="User name")
    sys_code: Optional[str] = Field(default=None, description="System code")
    gmt_created: Optional[str] = Field(default=None, description="Creation time")
    gmt_modified: Optional[str] = Field(default=None, description="Last modified time")


def _entity_to_response(entity: ConnectorInstanceEntity) -> ConnectorResponse:
    """Convert a ConnectorInstanceEntity to a ConnectorResponse."""
    config = None
    if entity.config_json:
        try:
            config = json.loads(entity.config_json)
        except Exception:
            config = None

    gmt_created = None
    if entity.gmt_created:
        gmt_created = entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")

    gmt_modified = None
    if entity.gmt_modified:
        gmt_modified = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")

    return ConnectorResponse(
        connector_id=entity.connector_id,
        connector_type=entity.connector_type,
        display_name=entity.display_name or "",
        status=entity.status or "active",
        config=config,
        user_name=entity.user_name,
        sys_code=entity.sys_code,
        gmt_created=gmt_created,
        gmt_modified=gmt_modified,
    )


class ConnectorService(
    BaseService[ConnectorInstanceEntity, ConnectorCreateRequest, ConnectorUpdateRequest]
):
    """Service for managing connector instances."""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        dao: Optional[ConnectorInstanceDao] = None,
    ):
        self._serve_config = config or ServeConfig()
        self._dao = dao or ConnectorInstanceDao(self._serve_config)
        self._credential_store = CredentialStore(system_app=system_app)
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service."""
        self._system_app = system_app
        self._credential_store = CredentialStore(system_app=system_app)

    def after_start(self):
        """Rehydrate active connectors into the runtime connector manager."""
        super_after_start = getattr(super(), "after_start", None)
        if callable(super_after_start):
            super_after_start()

        connector_manager = self.system_app.get_component(
            "connector_manager",
            ConnectorManager,
            default_component=None,
        )
        if connector_manager is None:
            return

        loop = get_or_create_event_loop()
        with self._dao.session() as session:
            active_connectors = []
            for entity in (
                session.query(ConnectorInstanceEntity)
                .filter(ConnectorInstanceEntity.status == "active")
                .all()
            ):
                extra_config: Optional[Dict[str, Any]] = None
                if entity.config_json:
                    try:
                        extra_config = json.loads(entity.config_json)
                    except Exception:
                        extra_config = None
                active_connectors.append(
                    {
                        "connector_id": entity.connector_id,
                        "connector_type": entity.connector_type,
                        "display_name": entity.display_name,
                        "encrypted_credentials": entity.encrypted_credentials,
                        "encryption_salt": entity.encryption_salt,
                        "config": extra_config,
                    }
                )

        for connector in active_connectors:
            try:
                credentials = self._credential_store.decrypt(
                    connector["encrypted_credentials"],
                    connector["encryption_salt"],
                )
                loop.run_until_complete(
                    connector_manager.create_connector(
                        connector_type=connector["connector_type"],
                        credentials=credentials,
                        name=connector["display_name"],
                        extra_config=connector.get("config"),
                        connector_id=connector["connector_id"],
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to rehydrate connector '%s': %s",
                    connector["connector_id"],
                    exc,
                )

    @property
    def dao(
        self,
    ) -> BaseDao[
        ConnectorInstanceEntity, ConnectorCreateRequest, ConnectorUpdateRequest
    ]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> BaseServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def create_connector(self, request: ConnectorCreateRequest) -> ConnectorResponse:
        """Create a new connector instance.

        Args:
            request (ConnectorCreateRequest): The create request.

        Returns:
            ConnectorResponse: The created connector response.
        """
        connector_id = str(uuid.uuid4())
        encryption_salt = self._credential_store.generate_salt()
        encrypted_credentials = self._credential_store.encrypt(
            {k: str(v) for k, v in request.credentials.items()},
            encryption_salt,
        )
        config_json = json.dumps(request.config) if request.config else None

        entity = ConnectorInstanceEntity(
            connector_id=connector_id,
            connector_type=request.connector_type,
            display_name=request.display_name,
            encrypted_credentials=encrypted_credentials,
            encryption_salt=encryption_salt,
            status="active",
            config_json=config_json,
            user_name=request.user_name,
            sys_code=request.sys_code,
        )

        with self._dao.session() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)

            connector_manager = self.system_app.get_component(
                "connector_manager",
                ConnectorManager,
                default_component=None,
            )
            if connector_manager is not None:
                loop = get_or_create_event_loop()
                loop.run_until_complete(
                    connector_manager.create_connector(
                        connector_type=request.connector_type,
                        credentials=request.credentials,
                        name=request.display_name,
                        extra_config=request.config,
                        connector_id=connector_id,
                    )
                )

            return _entity_to_response(entity)

    def list_connectors(
        self,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
    ) -> List[ConnectorResponse]:
        """List all connector instances, optionally filtered by user_name/sys_code.

        Args:
            user_name (Optional[str]): Filter by user name.
            sys_code (Optional[str]): Filter by system code.

        Returns:
            List[ConnectorResponse]: List of connector responses.
        """
        with self._dao.session() as session:
            query = session.query(ConnectorInstanceEntity)
            if user_name is not None:
                query = query.filter(ConnectorInstanceEntity.user_name == user_name)
            if sys_code is not None:
                query = query.filter(ConnectorInstanceEntity.sys_code == sys_code)
            entities = query.all()
            return [_entity_to_response(e) for e in entities]

    def get_connector(self, connector_id: str) -> Optional[ConnectorResponse]:
        """Get a connector instance by ID.

        Args:
            connector_id (str): The connector UUID.

        Returns:
            Optional[ConnectorResponse]: The connector response or None if not found.
        """
        with self._dao.session() as session:
            entity = (
                session.query(ConnectorInstanceEntity)
                .filter(ConnectorInstanceEntity.connector_id == connector_id)
                .first()
            )
            if entity is None:
                return None
            return _entity_to_response(entity)

    def update_connector(
        self, connector_id: str, request: ConnectorUpdateRequest
    ) -> ConnectorResponse:
        """Update a connector instance.

        Args:
            connector_id (str): The connector UUID.
            request (ConnectorUpdateRequest): The update request.

        Returns:
            ConnectorResponse: The updated connector response.

        Raises:
            ValueError: If the connector is not found.
        """
        with self._dao.session() as session:
            entity = (
                session.query(ConnectorInstanceEntity)
                .filter(ConnectorInstanceEntity.connector_id == connector_id)
                .first()
            )
            if entity is None:
                raise ValueError(f"Connector '{connector_id}' not found")

            if request.display_name is not None:
                entity.display_name = request.display_name
            if request.credentials is not None:
                entity.encryption_salt = self._credential_store.generate_salt()
                entity.encrypted_credentials = self._credential_store.encrypt(
                    {k: str(v) for k, v in request.credentials.items()},
                    entity.encryption_salt,
                )
            if request.config is not None:
                entity.config_json = json.dumps(request.config)

            session.flush()
            session.refresh(entity)
            return _entity_to_response(entity)

    def delete_connector(self, connector_id: str) -> None:
        """Delete a connector instance.

        Args:
            connector_id (str): The connector UUID.

        Raises:
            ValueError: If the connector is not found.
        """
        with self._dao.session() as session:
            entity = (
                session.query(ConnectorInstanceEntity)
                .filter(ConnectorInstanceEntity.connector_id == connector_id)
                .first()
            )
            if entity is None:
                raise ValueError(f"Connector '{connector_id}' not found")
            session.delete(entity)

    def test_connection(self, connector_id: str) -> bool:
        """Test the connection for a connector instance.

        Args:
            connector_id (str): The connector UUID.

        Returns:
            bool: True if connection test passes (placeholder implementation).
        """
        # Placeholder: verify connector exists, actual connection test in T15
        connector = self.get_connector(connector_id)
        if connector is None:
            raise ValueError(f"Connector '{connector_id}' not found")
        return True
