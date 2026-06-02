"""ConnectorManager — aggregates ConnectorCatalog, CredentialStore and ConfirmationInterceptor."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypedDict

from dbgpt.agent.resource.tool.base import BaseTool
from dbgpt.component import BaseComponent, SystemApp

from .catalog import ConnectorCatalog
from .confirmation import ConfirmationInterceptor, ConfirmationRegistry
from .credential import CredentialStore

if TYPE_CHECKING:
    from dbgpt.agent.resource.tool.pack import MCPToolPack

logger = logging.getLogger(__name__)

# Hard ceiling on initial MCP handshake (tools/list) during create_connector.
# Without this, a stuck SSE/Streamable-HTTP server keeps the FastAPI handler
# blocked indefinitely (the create path runs the coroutine via
# ``loop.run_until_complete`` on a worker thread, so a hang there leaves the
# user staring at a spinner with no eventual response). 15s is generous for
# real MCP servers but short enough that misconfigured ones fail fast.
_CONNECTOR_PRELOAD_TIMEOUT_S = 15.0


class ConnectorToolArgSummary(TypedDict):
    """Per-argument schema for a single connector tool."""

    type: str
    required: bool
    description: str


class ConnectorToolSummary(TypedDict):
    """Lightweight, prompt-friendly summary of a single connector tool."""

    name: str
    """Full routing name (``mcp__{prefix}__{original_name}``) — what LLMs
    invoke. Includes the DB-GPT-internal namespace prefix added by
    :meth:`ConnectorManager._apply_tool_prefix`."""

    original_name: str
    """The tool's name as declared by the MCP server itself (no prefix).
    This is what users see when inspecting tools — it matches what the MCP
    server returns from its own ``tools/list``."""

    description: str
    args: Dict[str, ConnectorToolArgSummary]


def _strip_routing_prefix(name: str) -> str:
    """Strip the ``mcp__{prefix}__`` routing prefix added by
    :meth:`ConnectorManager._apply_tool_prefix`.

    The prefix format is stable: ``name.split('__', 2)`` reliably yields
    ``['mcp', '{prefix}', '{original_name}']`` because :func:`_slugify`
    never produces ``__`` in the ``{prefix}`` segment.

    Falls back to *name* unchanged when the routing prefix is absent
    (e.g. a non-MCP tool that somehow leaked into a pack).
    """
    if name.startswith("mcp__"):
        parts = name.split("__", 2)
        if len(parts) == 3:
            return parts[2]
    return name


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
        # Per-connector extra_config snapshot — kept so list_active() can
        # surface user-provided fields (e.g. custom_mcp's optional
        # ``description``) that are not stored in the catalog entry or
        # encrypted credential blob. Keyed by connector_id; cleared in
        # remove_connector. Holds a shallow copy to insulate the manager
        # from later mutations by the caller.
        self._extra_configs: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Tool prefix helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_custom_connector_type(connector_type: str) -> bool:
        """Return True iff *connector_type* is a custom (user-defined) MCP type.

        A custom connector type is identified by a non-empty ``custom_`` prefix
        followed by a non-empty suffix, e.g. ``"custom_mcp"``,
        ``"custom_arxiv"``. The bare prefix ``"custom_"`` and non-string inputs
        return False.

        Args:
            connector_type (str): The connector type identifier.

        Returns:
            bool: True if *connector_type* is a custom MCP type.
        """
        if not isinstance(connector_type, str):
            return False
        if not connector_type.startswith("custom_"):
            return False
        # Reject bare "custom_" (no suffix).
        return len(connector_type) > len("custom_")

    def _has_multiple_instances_of_type(self, connector_type: str) -> bool:
        """True if at least one other connector of the same type is already active."""
        return any(t == connector_type for cid, t in self._connector_types.items())

    def compute_tool_prefix(
        self,
        connector_type: str,
        display_name: str,
        connector_id: str,
    ) -> str:
        """Return the connector identifier portion (between the two ``__``) of the tool name.

        Tool name format: ``mcp__{prefix}__{original_tool_name}``.

        Prefix rules (the ``{prefix}`` portion only):
        - Built-in, single instance: ``{connector_type}``
        - Built-in, multiple instances: ``{connector_type}-{slug(display_name)}``
        - Custom (type starts with ``custom_``): ``{slug(display_name)}``
        - Fallback when slug is empty: first 6 chars of *connector_id*

        Note: The full tool name is composed in ``_apply_tool_prefix`` by adding
        the ``mcp__`` prefix and using ``__`` as separator between prefix and
        original tool name, e.g.:
          - ``mcp__github__create_issue``
          - ``mcp__github-acme__create_issue``
          - ``mcp__my-arxiv__search_papers``
        """
        is_custom = self.is_custom_connector_type(connector_type)
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
        """Rename every tool in *pack* to ``mcp__{prefix}__{original_name}`` and update tool_server_map.

        Format chosen to mirror Claude Code's MCP tool naming convention
        (``mcp__<server>__<tool>``):
        - ``mcp__`` prefix makes the tool's MCP origin obvious to the LLM and ops.
        - Double-underscore separators (``__``) avoid ambiguity when the original
          tool name itself contains underscores (e.g. ``search_papers``).
        - Stable parse: ``name.split('__', 2)`` reliably yields
          ``['mcp', prefix, tool_name]``.

        Idempotent: a tool already named ``mcp__{prefix}__...`` is left as-is.
        """
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
            prefixed = f"mcp__{prefix}__{old_name}"
            # Skip if already prefixed (idempotency)
            if old_name.startswith(f"mcp__{prefix}__"):
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
        extra_config: Optional[Dict[str, Any]] = None,
        connector_id: Optional[str] = None,
    ) -> str:
        """Validate, encrypt and activate a new connector instance.

        Two branches are supported:

        * **Built-in catalog connector** — ``connector_type`` must exist in the
          loaded catalog (e.g. ``"feishu"``, ``"github"``).  Header mapping is
          taken from the catalog entry.  ``extra_config`` **must** supply
          ``server_uri`` — catalog entries are templates only and do not
          provide default server URIs.
        * **User-defined custom MCP server** — when
          ``connector_type == "custom_mcp"``, ``extra_config`` must supply
          ``server_uri`` (the SSE endpoint).  Header mapping is derived from
          ``extra_config['auth_type']`` (``"none"``, ``"bearer"`` or
          ``"token"``) and the optional ``extra_config['header_name']``.

        Args:
            connector_type (str): A catalog key, or the literal
                ``"custom_mcp"`` for user-defined MCP servers.
            credentials (Dict[str, Any]): Raw credential key/value pairs as
                required by the connector's ``auth.fields`` spec.
            name (Optional[str]): Human-readable label for this connector
                instance.  Defaults to *connector_type*.
            extra_config (Optional[Dict[str, Any]]): Required for all
                connector types (built-in catalog types and ``custom_mcp``).
                Must contain ``server_uri`` (str).  For ``custom_mcp`` also
                accepts ``auth_type`` / ``header_name``.  Built-in types pull
                ``header_mapping`` from catalog ``auth.header_mapping``.
            connector_id (Optional[str]): Preserve a known UUID (used by
                rehydration during process startup).  When ``None``, a fresh
                hex token is generated.

        Returns:
            str: A unique connector_id (hex string or caller-supplied) that
            identifies this live connector instance.

        Raises:
            ValueError: When *connector_type* is not found in the catalog and
                is not ``"custom_mcp"``, or when ``custom_mcp`` is requested
                without a valid ``server_uri`` in ``extra_config``.
            ValueError: When ``extra_config.server_uri`` is missing (catalog
                templates do not provide default URIs).
        """
        connector_id = connector_id or secrets.token_hex(16)

        salt = self._credential_store.generate_salt()
        self._salts[connector_id] = salt
        str_credentials: Dict[str, str] = {k: str(v) for k, v in credentials.items()}

        # server_uri is mandatory for ALL connector types — catalog entries are
        # display-only templates; the user always supplies the endpoint via the
        # unified ConnectorForm.
        if not extra_config or not extra_config.get("server_uri"):
            raise ValueError(
                f"Connector type '{connector_type}' requires extra_config.server_uri"
            )
        server_uri = extra_config["server_uri"]

        # Resolve catalog entry (None for custom_mcp). Unknown built-in types
        # are rejected; custom_mcp bypasses the catalog entirely.
        if connector_type == "custom_mcp":
            entry = None
        else:
            entry = self._catalog.get(connector_type)
            if entry is None:
                available = [e.type for e in self._catalog.list()]
                raise ValueError(
                    f"Unknown connector type '{connector_type}'. "
                    f"Available types: {available} "
                    f"(or 'custom_mcp' for user-defined MCP servers)"
                )

        if entry is not None:
            display_name = name or entry.display_name
            catalog_transport = (
                entry.mcp_server.transport if entry.mcp_server else "sse"
            )
        else:
            display_name = name or "Custom MCP"
            catalog_transport = "sse"
        # extra_config.transport always wins, so users can adopt a
        # streamable_http endpoint of a service whose template still says SSE
        # (and vice-versa) without us having to ship a new catalog.
        transport = extra_config.get("transport") or catalog_transport

        # Unified auth_type → header_mapping derivation. Was previously
        # custom_mcp-only; built-in templates now go through the same path so
        # users pick the auth scheme that matches their concrete MCP server,
        # rather than relying on a catalog-baked guess.
        auth_type = extra_config.get("auth_type", "none")
        if auth_type == "bearer":
            header_mapping = {"token": "Authorization"}
            # Auto-prefix Bearer if not already present.
            token_val = str_credentials.get("token", "")
            if token_val and not token_val.startswith("Bearer "):
                str_credentials["token"] = f"Bearer {token_val}"
        elif auth_type == "token":
            header_mapping = {"token": extra_config.get("header_name", "Authorization")}
        else:  # auth_type == "none"
            header_mapping = {}

        self._credential_store.encrypt(str_credentials, salt)

        headers: Dict[str, str] = {}
        for field_name, header_name in header_mapping.items():
            field_value = str_credentials.get(field_name)
            if field_value is not None:
                headers[header_name] = field_value

        # Import lazily to avoid circular dependency at module load time
        from dbgpt.agent.resource.tool.pack import MCPToolPack

        pack_name = display_name
        pack = MCPToolPack(
            mcp_servers=server_uri,
            default_headers=headers,
            name=pack_name,
            transport=transport,
        )

        try:
            # Bound the handshake — see _CONNECTOR_PRELOAD_TIMEOUT_S for why.
            # asyncio.TimeoutError → caught by the broad except below and
            # surfaced as ConnectorStatus.error, which is the same UX as a
            # network failure or auth rejection (the user retries from the UI).
            await asyncio.wait_for(
                pack.preload_resource(),
                timeout=_CONNECTOR_PRELOAD_TIMEOUT_S,
            )
            prefix = self.compute_tool_prefix(connector_type, pack_name, connector_id)
            self._apply_tool_prefix(pack, prefix, pack_name)
            self._active_packs[connector_id] = pack
            self._statuses[connector_id] = ConnectorStatus.active
            self._connector_types[connector_id] = connector_type
            # Snapshot the user-supplied extra_config (description, etc.) so
            # list_active() can surface fields beyond what the catalog or the
            # encrypted credential store provides. dict() = shallow copy to
            # decouple from later caller mutations.
            self._extra_configs[connector_id] = dict(extra_config or {})
        except asyncio.TimeoutError:
            self._statuses[connector_id] = ConnectorStatus.error
            logger.error(
                "Timeout activating connector '%s' (type=%s, transport=%s) "
                "after %.1fs — MCP server did not respond to handshake",
                pack_name,
                connector_type,
                transport,
                _CONNECTOR_PRELOAD_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001
            self._statuses[connector_id] = ConnectorStatus.error
            logger.error(
                "Failed to activate connector '%s' (type=%s, transport=%s): %s",
                pack_name,
                connector_type,
                transport,
                exc,
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
        self._extra_configs.pop(connector_id, None)
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

    def _tool_summary_for(
        self, connector_id: str
    ) -> Optional[List[ConnectorToolSummary]]:
        """Return the per-tool summary list for one active connector.

        Args:
            connector_id (str): Connector instance id.

        Returns:
            Optional[List[ConnectorToolSummary]]: A list of structurally-shaped
            tool summaries when *connector_id* is in ``_active_packs``;
            ``None`` otherwise. Shape matches the ``tools`` array entry in
            :meth:`list_active`.
        """
        pack = self._active_packs.get(connector_id)
        if pack is None:
            return None
        # Build per-tool summaries, deduplicating by `original_name`.
        #
        # Why dedup is needed: ``MCPToolPack._resources`` can end up holding
        # the same logical tool under two keys when ``preload_resource()``
        # runs more than once after ``_apply_tool_prefix`` has already
        # renamed the original entry — e.g. activate populates
        # ``_resources["mcp__svc__search_papers"]`` and then a later
        # ``test_connection`` re-issues ``tools/list`` and adds
        # ``_resources["search_papers"]`` (raw name, no prefix). Both keys
        # then surface here. Until the pack itself is made re-entry safe,
        # we collapse duplicates on the user-visible name, preferring the
        # entry that already carries the routing prefix (the canonical one
        # an LLM would actually invoke).
        by_original: Dict[str, ConnectorToolSummary] = {}
        for tool in pack.sub_resources:
            if not isinstance(tool, BaseTool):
                continue
            original = _strip_routing_prefix(tool.name)
            is_prefixed = tool.name != original
            summary: ConnectorToolSummary = {
                "name": tool.name,
                "original_name": original,
                "description": tool.description,
                "args": {
                    k: {
                        "type": getattr(v, "type", "any"),
                        "required": getattr(v, "required", False),
                        "description": getattr(v, "description", ""),
                    }
                    for k, v in (getattr(tool, "args", {}) or {}).items()
                },
            }
            existing = by_original.get(original)
            if existing is None:
                by_original[original] = summary
            elif is_prefixed and existing["name"] == existing["original_name"]:
                # We had the raw-name version; replace with the prefixed one.
                by_original[original] = summary
            # else: keep the existing (already prefixed) entry.
        return list(by_original.values())

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
            tools = self._tool_summary_for(connector_id) or []
            # Description precedence:
            #   1. extra_config.description (user-authored, custom_mcp)
            #   2. catalog entry description (built-in templates)
            #   3. empty string (falls back to "(no description)" in prompt)
            user_desc = self._extra_configs.get(connector_id, {}).get("description")
            description = user_desc or (entry.description if entry else "") or ""
            result.append(
                {
                    "connector_id": connector_id,
                    "name": pack.name,
                    "connector_type": connector_type,
                    "description": description,
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
