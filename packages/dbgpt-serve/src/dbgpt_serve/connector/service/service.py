"""Connector service for managing external connector instances."""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from dbgpt.agent.resource.connector.credential import CredentialStore
from dbgpt.agent.resource.connector.manager import ConnectorManager, ConnectorStatus
from dbgpt.agent.resource.tool.base import BaseTool
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
    status: str = Field(
        ...,
        description="Status: active / error / disconnected / needs_reactivation",
    )
    is_custom: bool = Field(
        default=False,
        description="True iff connector_type is a custom (user-defined) MCP type",
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional extra config"
    )
    user_name: Optional[str] = Field(default=None, description="User name")
    sys_code: Optional[str] = Field(default=None, description="System code")
    gmt_created: Optional[str] = Field(default=None, description="Creation time")
    gmt_modified: Optional[str] = Field(default=None, description="Last modified time")


class ConnectorToolsResponse(BaseModel):
    """Response model for the per-connector tool listing endpoint.

    ``state`` indicates the runtime status of the underlying tool pack:

    * ``"active"`` — pack is loaded in the runtime ConnectorManager.
    * ``"inactive"`` — pack is not currently loaded (failed activation /
      removed). ``tools`` is an empty list in this case.
    * ``"not_mcp"`` — reserved for future non-MCP connector types; unreachable
      in v1 since every connector is MCP-based today.
    """

    connector_id: str = Field(..., description="Connector UUID")
    state: Literal["active", "inactive", "not_mcp"] = Field(
        ...,
        description="Runtime tool-pack state for the connector",
    )
    # Structurally a List[ConnectorToolSummary]; declared as List[Dict[str, Any]]
    # because Pydantic v2 cannot directly serialise nested TypedDicts.
    tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tool summaries; each entry shaped like ConnectorToolSummary",
    )


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
        is_custom=ConnectorManager.is_custom_connector_type(entity.connector_type),
        config=config,
        user_name=entity.user_name,
        sys_code=entity.sys_code,
        gmt_created=gmt_created,
        gmt_modified=gmt_modified,
    )


# Per-tool args JSON cap. When exceeded, the tool's args block is replaced with
# a ``_truncated`` marker to keep response payloads bounded for very large
# JSON Schemas while preserving the top-level shape consumers depend on.
_TOOL_ARGS_BYTE_CAP = 8192


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
            except ValueError as exc:
                # Catalog downgrade compatibility: pre-1.5 instances may lack
                # server_uri in config_json. Mark them as needs_reactivation so
                # UI can prompt user.
                msg = str(exc)
                if "requires extra_config.server_uri" in msg:
                    try:
                        with self._dao.session() as session:
                            row = (
                                session.query(ConnectorInstanceEntity)
                                .filter(
                                    ConnectorInstanceEntity.connector_id
                                    == connector["connector_id"]
                                )
                                .first()
                            )
                            if row is not None:
                                row.status = "needs_reactivation"
                                session.flush()
                    except Exception:
                        logger.exception(
                            "Failed to mark connector '%s' as needs_reactivation",
                            connector["connector_id"],
                        )
                    logger.warning(
                        "Connector '%s' (type=%s) needs reactivation: missing "
                        "server_uri in config_json (likely created before "
                        "catalog downgrade)",
                        connector["connector_id"],
                        connector["connector_type"],
                    )
                else:
                    logger.warning(
                        "Failed to rehydrate connector '%s': %s",
                        connector["connector_id"],
                        exc,
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

            credentials_changed = False
            # P0-3 fix: merge credentials instead of overwriting.
            # Empty dict / None means "no credential changes", do nothing.
            if request.credentials is not None and len(request.credentials) > 0:
                try:
                    existing = (
                        self._credential_store.decrypt(
                            entity.encrypted_credentials,
                            entity.encryption_salt,
                        )
                        or {}
                    )
                except Exception:
                    logger.warning(
                        "Failed to decrypt existing credentials for '%s'; "
                        "proceeding with new credentials only",
                        connector_id,
                    )
                    existing = {}
                # New fields override existing; existing fields survive when
                # new value is empty/missing.
                merged = {
                    **existing,
                    **{k: str(v) for k, v in request.credentials.items()},
                }
                entity.encryption_salt = self._credential_store.generate_salt()
                entity.encrypted_credentials = self._credential_store.encrypt(
                    merged,
                    entity.encryption_salt,
                )
                credentials_changed = True

            config_changed = False
            if request.config is not None:
                entity.config_json = json.dumps(request.config)
                config_changed = True

            # P0-1 fix: re-activate manager if credentials/config changed,
            # so the connector becomes usable AND the status reflects reality.
            if credentials_changed or config_changed:
                previous_status = entity.status
                entity.status = "active"

                connector_manager = self.system_app.get_component(
                    "connector_manager",
                    ConnectorManager,
                    default_component=None,
                )
                if connector_manager is not None:
                    try:
                        decrypted_creds = (
                            self._credential_store.decrypt(
                                entity.encrypted_credentials,
                                entity.encryption_salt,
                            )
                            or {}
                        )
                    except Exception:
                        decrypted_creds = {}

                    extra_config: Optional[Dict[str, Any]] = None
                    if entity.config_json:
                        try:
                            extra_config = json.loads(entity.config_json)
                        except Exception:
                            extra_config = None

                    loop = get_or_create_event_loop()
                    try:
                        loop.run_until_complete(
                            connector_manager.remove_connector(connector_id)
                        )
                    except Exception:
                        pass  # remove is no-op if connector_id not active
                    try:
                        loop.run_until_complete(
                            connector_manager.create_connector(
                                connector_type=entity.connector_type,
                                credentials=decrypted_creds,
                                name=entity.display_name,
                                extra_config=extra_config,
                                connector_id=connector_id,
                            )
                        )
                    except Exception as exc:
                        entity.status = "error"
                        logger.warning(
                            "Re-activation failed for connector '%s' "
                            "(was %s, now error): %s",
                            connector_id,
                            previous_status,
                            exc,
                        )

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

    def list_tools(self, connector_id: str) -> ConnectorToolsResponse:
        """Return the tool summaries for a single connector.

        Args:
            connector_id (str): The connector UUID.

        Returns:
            ConnectorToolsResponse: Wrapping ``state`` and ``tools``. When the
            pack is not present in the runtime manager (e.g. activation failed
            after restart), ``state`` is ``"inactive"`` and ``tools`` is empty.

        Raises:
            HTTPException: 404 when *connector_id* is not present in the DB.
        """
        if self.get_connector(connector_id) is None:
            raise HTTPException(
                status_code=404, detail=f"Connector '{connector_id}' not found"
            )

        connector_manager = self.system_app.get_component(
            "connector_manager",
            ConnectorManager,
            default_component=None,
        )

        # Forward-compat: in v1 every connector is MCP-based, so we never
        # produce "not_mcp" — the branch is here for future non-MCP types.
        state: Literal["active", "inactive", "not_mcp"]
        tools: List[Dict[str, Any]] = []

        summary: Optional[List[Dict[str, Any]]] = None
        if connector_manager is not None:
            summary = connector_manager._tool_summary_for(connector_id)

        if summary is None:
            state = "inactive"
        else:
            # Apply per-tool args cap. Marker stays inside ``args`` to keep the
            # top-level tool entry shape stable for the caller.
            for tool in summary:
                args = tool.get("args") or {}
                args_json = json.dumps(args)
                byte_count = len(args_json.encode("utf-8"))
                if byte_count > _TOOL_ARGS_BYTE_CAP:
                    tool["args"] = {
                        "_truncated": True,
                        "byte_count": byte_count,
                    }
            tools = summary

            # Cross-check DB status: if the row says "active" or any liveness
            # state where the pack is in fact loaded, honour the pack presence
            # as the source of truth (DB rows can drift after manager restarts).
            current_status = (
                connector_manager._statuses.get(connector_id)
                if connector_manager is not None
                else None
            )
            state = "active" if current_status == ConnectorStatus.active else "inactive"

        return ConnectorToolsResponse(
            connector_id=connector_id,
            state=state,
            tools=tools,
        )

    def _heal_status_to_active(self, connector_id: str) -> None:
        """Refresh a non-active row to 'active' after a successful liveness probe.

        Best-effort: a DB write failure here must NOT bubble up and turn a
        successful test_connection into a failure response to the user.
        Skips the write when status is already 'active' to avoid pointless
        UPDATEs (and gmt_modified churn) on every test click.
        """
        try:
            with self._dao.session() as session:
                entity = (
                    session.query(ConnectorInstanceEntity)
                    .filter(ConnectorInstanceEntity.connector_id == connector_id)
                    .first()
                )
                if entity is None or entity.status == "active":
                    return
                previous_status = entity.status
                entity.status = "active"
                session.flush()
                logger.info(
                    "Connector '%s' status healed from '%s' to 'active' "
                    "after successful test_connection",
                    connector_id,
                    previous_status,
                )
        except Exception:
            logger.exception(
                "Failed to heal status for connector '%s'; "
                "test_connection result is unaffected",
                connector_id,
            )

    async def test_connection(self, connector_id: str) -> Dict[str, Any]:
        """Test the connection for a connector instance — actual SSE handshake.

        Args:
            connector_id (str): The connector UUID.

        Returns:
            Dict[str, Any]: ``{"success": bool, "message": str}``.

        Raises:
            ValueError: If the connector is not found in DB.
        """
        connector = self.get_connector(connector_id)
        if connector is None:
            raise ValueError(f"Connector '{connector_id}' not found")

        cm = self.system_app.get_component(
            "connector_manager", ConnectorManager, default_component=None
        )
        if cm is None:
            return {"success": False, "message": "ConnectorManager 未就绪"}

        pack = cm.get_connector_tools(connector_id)
        if pack is None:
            return {
                "success": False,
                "message": "连接器未激活,请检查 server_uri/凭证后重新激活",
            }

        try:
            # 真实测试:重新跑 SSE handshake + tools/list
            await asyncio.wait_for(pack.preload_resource(), timeout=10.0)

            tool_count = sum(1 for t in pack.sub_resources if isinstance(t, BaseTool))

            # Self-heal: a successful handshake proves the connector works now.
            # Without this, a row stamped 'error' by a past transient PUT
            # failure stays 'error' forever — nothing else flips it back.
            self._heal_status_to_active(connector_id)

            return {
                "success": True,
                "message": f"连接成功,发现 {tool_count} 个工具",
            }
        except asyncio.TimeoutError:
            logger.warning("test_connection timeout (>10s) for '%s'", connector_id)
            return {"success": False, "message": "连接超时(>10s)"}
        except Exception as exc:
            logger.warning(
                "test_connection failed for '%s': %s",
                connector_id,
                exc,
                exc_info=True,
            )
            return {
                "success": False,
                "message": "连接失败,请检查 server_uri 与凭证(详情见服务端日志)",
            }
