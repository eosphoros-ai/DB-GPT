"""Pydantic schemas for the connector HTTP API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConnectorTypeOption(BaseModel):
    """Connector type entry returned by GET /types.

    Built-in entries are sourced from the loaded catalog;
    the `custom_mcp` entry is a synthetic placeholder for user-defined MCP servers.
    """

    type: str
    display_name: str
    description: str
    icon: Optional[str] = None
    category: str
    is_custom: bool = False
    auth_fields: List[Dict[str, Any]]
