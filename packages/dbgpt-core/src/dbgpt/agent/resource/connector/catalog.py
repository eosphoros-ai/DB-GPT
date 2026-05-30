"""Connector catalog — loads connector definitions from catalog.json."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class McpServerConfig(BaseModel):
    server_uri: Optional[str] = None
    transport: str = "sse"


class AuthField(BaseModel):
    name: str
    label: str
    type: str
    required: bool = True


class AuthConfig(BaseModel):
    type: str
    fields: List[AuthField]
    header_mapping: Dict[str, str] = {}


class ConnectorCatalogEntry(BaseModel):
    type: str
    display_name: str
    description: str
    icon: str
    category: str
    mcp_server: McpServerConfig
    auth: AuthConfig
    confirm_actions: List[str] = []
    read_actions: List[str] = []


class ConnectorCatalog:
    def __init__(self) -> None:
        self._entries: Dict[str, ConnectorCatalogEntry] = {}

    def load(self, path: str) -> None:
        catalog_path = Path(path)
        if not catalog_path.exists():
            raise FileNotFoundError(f"Connector catalog not found: {path}")
        try:
            raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in catalog file {path}: {exc}") from exc

        connectors = raw.get("connectors")
        if not isinstance(connectors, list):
            raise ValueError(
                f"catalog.json must contain a top-level 'connectors' list, got: {type(connectors)}"
            )

        self._entries = {}
        for item in connectors:
            entry = ConnectorCatalogEntry.model_validate(item)
            self._entries[entry.type] = entry

        logger.debug("Loaded %d connectors from %s", len(self._entries), path)

    def get(self, connector_type: str) -> Optional[ConnectorCatalogEntry]:
        return self._entries.get(connector_type)

    def list(self) -> List[ConnectorCatalogEntry]:
        return list(self._entries.values())

    def list_by_category(self, category: str) -> List[ConnectorCatalogEntry]:
        return [e for e in self._entries.values() if e.category == category]
