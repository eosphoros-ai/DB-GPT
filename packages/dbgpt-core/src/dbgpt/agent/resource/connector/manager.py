"""ConnectorManager — aggregates ConnectorCatalog, CredentialStore and ConfirmationInterceptor."""

from __future__ import annotations

import logging
import re
import secrets
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dbgpt.agent.resource.tool.base import BaseTool
from dbgpt.component import BaseComponent, SystemApp

from .catalog import ConnectorCatalog
from .confirmation import ConfirmationInterceptor, ConfirmationRegistry
from .credential import CredentialStore

if TYPE_CHECKING:
    from dbgpt.agent.resource.tool.pack import MCPToolPack

logger = logging.getLogger(__name__)


class ConnectorStatus(str, Enum):
    """Status of a live connector instance.

    Attributes:
        active: Connector is running and tools are available.
        error: Connector failed to start or encountered a fatal error.
        disconnected: Connector was explicitly removed or gracefully stopped.
    """

    active = "active"
    error = "error"
    disconnected = "disconnected"


def _slugify(text: str) -> str:
    """Convert *text* to a lowercase ASCII slug.

    Rules: lowercase, replace whitespace and underscores with ``-``,
    strip characters outside ``[a-z0-9-]``, collapse consecutive dashes.
    """
    s = text.lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    return s


class ConnectorManager(BaseComponent):
    """Core manager that aggregates catalog, credential store and confirmation system.

    ConnectorManager is a ``BaseComponent`` that owns:

    * a :class:`~.catalog.ConnectorCatalog` with available connector types,
    * a :class:`~.credential.CredentialStore` for encrypted credential handling,
    * a :class:`~.confirmation.ConfirmationInterceptor` and
      :class:`~.confirmation.ConfirmationRegistry` for human-in-the-loop flows,
    * a live registry of :class:`~dbgpt.agent.resource.tool.pack.MCPToolPack`
      instances keyed by connector_id.

    Example::

        manager = ConnectorManager(system_app)
        manager.load_catalog("/path/to/catalog.json")
        connector_id = await manager.create_connector(
            connector_type="feishu",
            credentials={"token": "my-token"},
            name="My Feishu",
        )
        pack = manager.get_connector_tools(connector_id)
    """

    name = "connector_manager"

    def __init__(self, system_app: Optional[SystemApp] = None) -> None:
        """Initialise internal sub-components.

        Args:
            system_app (Optional[SystemApp]): The system application instance.
                If provided, ``init_app`` is called immediately.
        """
        super().__init__(system_app)
        self._catalog: ConnectorCatalog = ConnectorCatalog()
        self._credential_store: CredentialStore = CredentialStore()
        self._confirmation: ConfirmationInterceptor = ConfirmationInterceptor(
            self._catalog
        )
        self._confirmation_registry: ConfirmationRegistry = ConfirmationRegistry()
        self._active_packs: Dict[str, "MCPToolPack"] = {}
        self._statuses: Dict[str, ConnectorStatus] = {}
        self._salts: Dict[str, str] = {}
        self._connector_types: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Tool prefix helpers
    # ------------------------------------------------------------------

    def _has_multiple_instances_of_type(self, connector_type: str) -> bool:
        """True if at least one other connector of the same type is already active."""
        return any(t == connector_type for cid, t in self._connector_types.items())

    def compute_tool_prefix(
        self,
        connector_type: str,
        display_name: str,
        connector_id: str,
    ) -> str:
        """Return the prefix to prepend to every tool name in this connector's pack.

        Prefix rules:
        - Built-in, single instance: ``{connector_type}``
        - Built-in, multiple instances: ``{connector_type}-{slug(display_name)}``
        - Custom (type starts with ``custom_``): ``{slug(display_name)}``
        - Fallback when slug is empty: first 6 chars of *connector_id*
        """
        is_custom = connector_type.startswith("custom_")
        slug = _slugify(display_name)

        if is_custom:
            return slug if slug else connector_id[:6]

        if self._has_multiple_instances_of_type(connector_type):
            suffix = slug if slug else connector_id[:6]
            return f"{connector_type}-{suffix}"

        return connector_type

    def _apply_tool_prefix(
        self, pack: "MCPToolPack", prefix: str, display_name: str
    ) -> None:
        """Rename every tool in *pack* to add the prefix and update tool_server_map."""
        new_server_map: Dict[str, str] = {}
        default_server = (
            pack._mcp_servers
            if isinstance(pack._mcp_servers, str)
            else (pack._mcp_servers[0] if pack._mcp_servers else "")
        )
        new_resources: Dict[str, Any] = {}

        for tool in list(pack.sub_resources):
            if not isinstance(tool, BaseTool):
                continue
            old_name = tool.name
            prefixed = f"{prefix}_{old_name}"
            # Skip if already prefixed (idempotency)
            if old_name.startswith(f"{prefix}_"):
                new_server_map[old_name] = pack.tool_server_map.get(
                    old_name, default_server
                )
                new_resources[old_name] = tool
                continue
            new_name = prefixed
            new_server_map[new_name] = pack.tool_server_map.get(
                old_name, default_server
            )
            # Rename tool internals
            tool._name = new_name
            if not tool._description.endswith(f"(via {display_name})"):
                tool._description = f"{tool._description} (via {display_name})"
            new_resources[new_name] = tool

        pack.tool_server_map = new_server_map
        pack._resources = new_resources

    def init_app(self, system_app: SystemApp) -> None:
        """Bind the manager to *system_app*.

        Args:
            system_app (SystemApp): The host system application.
        """
        self._system_app = system_app
        self._credential_store = CredentialStore(system_app=system_app)
        logger.debug("ConnectorManager initialised with system_app=%r", system_app)

    # ------------------------------------------------------------------
    # Catalog helpers
    # ------------------------------------------------------------------

    def get_catalog(self) -> ConnectorCatalog:
        """Public accessor for the catalog (used by /types endpoint).

        Returns:
            ConnectorCatalog: The loaded connector catalog.
        """
        return self._catalog

    def load_catalog(self, path: str) -> None:
        """Load connector type definitions from a *catalog.json* file.

        Args:
            path (str): Absolute or relative path to ``catalog.json``.

        Raises:
            FileNotFoundError: When *path* does not exist.
            ValueError: When the JSON is malformed or lacks a ``connectors`` list.
        """
        self._catalog.load(path)
        logger.info("Connector catalog loaded from %s", path)

    async def create_connector(
        self,
        connector_type: str,
        credentials: Dict[str, Any],
        name: Optional[str] = None,
    ) -> str:
        """Validate, encrypt and activate a new connector instance.

        Args:
            connector_type (str): A key that must exist in the loaded catalog
                (e.g. ``"feishu"``, ``"github"``).
            credentials (Dict[str, Any]): Raw credential key/value pairs as
                required by the connector's ``auth.fields`` spec.
            name (Optional[str]): Human-readable label for this connector
                instance.  Defaults to *connector_type*.

        Returns:
            str: A unique connector_id (hex string) that identifies this live
            connector instance.

        Raises:
            ValueError: When *connector_type* is not found in the catalog.
        """
        entry = self._catalog.get(connector_type)
        if entry is None:
            available = [e.type for e in self._catalog.list()]
            raise ValueError(
                f"Unknown connector type '{connector_type}'. "
                f"Available types: {available}"
            )

        connector_id = secrets.token_hex(16)

        salt = self._credential_store.generate_salt()
        self._salts[connector_id] = salt
        str_credentials: Dict[str, str] = {k: str(v) for k, v in credentials.items()}
        self._credential_store.encrypt(str_credentials, salt)

        headers: Dict[str, str] = {}
        for field_name, header_name in entry.auth.header_mapping.items():
            field_value = str_credentials.get(field_name)
            if field_value is not None:
                headers[header_name] = field_value

        # Import lazily to avoid circular dependency at module load time
        from dbgpt.agent.resource.tool.pack import MCPToolPack

        server_uri = entry.mcp_server.server_uri
        pack_name = name or connector_type
        pack = MCPToolPack(
            mcp_servers=server_uri,
            default_headers=headers,
            name=pack_name,
        )

        try:
            await pack.preload_resource()
            prefix = self.compute_tool_prefix(connector_type, pack_name, connector_id)
            self._apply_tool_prefix(pack, prefix, pack_name)
            self._active_packs[connector_id] = pack
            self._statuses[connector_id] = ConnectorStatus.active
            self._connector_types[connector_id] = connector_type
            tool_count = sum(
                1 for tool in pack.sub_resources if isinstance(tool, BaseTool)
            )
            logger.info(
                "Connector '%s' (id=%s, type=%s) activated with %d tools",
                pack_name,
                connector_id,
                connector_type,
                tool_count,
            )
        except Exception as exc:  # noqa: BLE001
            self._statuses[connector_id] = ConnectorStatus.error
            logger.error(
                "Failed to activate connector '%s' (type=%s): %s",
                pack_name,
                connector_type,
                exc,
                exc_info=True,
            )

        return connector_id

    async def remove_connector(self, connector_id: str) -> None:
        """Remove a live connector instance.

        Args:
            connector_id (str): The id previously returned by
                :meth:`create_connector`.
        """
        if connector_id not in self._active_packs:
            logger.warning(
                "remove_connector: connector_id '%s' not found in active packs",
                connector_id,
            )
            return

        self._statuses[connector_id] = ConnectorStatus.disconnected
        self._active_packs.pop(connector_id, None)
        self._salts.pop(connector_id, None)
        self._connector_types.pop(connector_id, None)
        # TODO(T6): cancel APScheduler jobs associated with connector_id
        logger.info("Connector id=%s removed", connector_id)

    def get_connector_tools(self, connector_id: str) -> Optional["MCPToolPack"]:
        """Return the :class:`~dbgpt.agent.resource.tool.pack.MCPToolPack` for a connector.

        Args:
            connector_id (str): Connector instance id.

        Returns:
            Optional[MCPToolPack]: The pack, or ``None`` when not found /
            not active.
        """
        return self._active_packs.get(connector_id)

    def get_all_tools(self) -> List["MCPToolPack"]:
        """Return all active :class:`~dbgpt.agent.resource.tool.pack.MCPToolPack` instances.

        Returns:
            List[MCPToolPack]: Snapshot of all currently active packs.
        """
        return list(self._active_packs.values())

    def list_active(self) -> List[Dict[str, Any]]:
        """Return prompt-ready summaries for all active connectors.

        Returns:
            List[Dict[str, Any]]: Lightweight connector metadata suitable for
            prompt composition or UI display.
        """
        result: List[Dict[str, Any]] = []
        for connector_id, pack in self._active_packs.items():
            connector_type = self._connector_types.get(connector_id, "unknown")
            entry = self._catalog.get(connector_type)
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                }
                for tool in pack.sub_resources
                if isinstance(tool, BaseTool)
            ]
            result.append(
                {
                    "connector_id": connector_id,
                    "name": pack.name,
                    "connector_type": connector_type,
                    "description": entry.description if entry else "",
                    "status": self._statuses.get(
                        connector_id, ConnectorStatus.disconnected
                    ).value,
                    "tools": tools,
                }
            )
        return result

    def get_confirmation_interceptor(self) -> ConfirmationInterceptor:
        """Return the shared :class:`~.confirmation.ConfirmationInterceptor`.

        Returns:
            ConfirmationInterceptor: The interceptor instance.
        """
        return self._confirmation

    def get_confirmation_registry(self) -> ConfirmationRegistry:
        """Return the shared :class:`~.confirmation.ConfirmationRegistry`.

        Returns:
            ConfirmationRegistry: The registry instance.
        """
        return self._confirmation_registry

    def get_status(self, connector_id: str) -> Optional[ConnectorStatus]:
        """Return the status of a connector instance.

        Args:
            connector_id (str): Connector instance id.

        Returns:
            Optional[ConnectorStatus]: Current status, or ``None`` when the
            connector_id is unknown.
        """
        return self._statuses.get(connector_id)
