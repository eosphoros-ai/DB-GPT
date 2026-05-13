"""Skill integration helpers for External Connectors.

Provides utilities to resolve connector tool packs required by a skill
and to check connector availability before skill execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from dbgpt.agent.resource.tool.pack import MCPToolPack

    from .manager import ConnectorManager

logger = logging.getLogger(__name__)


def resolve_skill_connectors(
    skill_config: Dict[str, Any],
    connector_manager: "ConnectorManager",
) -> List["MCPToolPack"]:
    """Resolve MCPToolPack instances required by a skill.

    Reads the ``required_tools`` field from *skill_config* (a list of
    connector type strings such as ``["yuque", "github"]``) and returns
    the corresponding active :class:`~.manager.ConnectorManager` tool
    packs.

    If a required connector type is not found among active connectors a
    warning is logged but execution is **not** blocked.

    Args:
        skill_config (Dict[str, Any]): Skill configuration dict that may
            contain a ``required_tools`` key with a list of connector
            type strings.
        connector_manager (ConnectorManager): The active connector
            manager instance.

    Returns:
        List[MCPToolPack]: Tool packs matching the required connector
        types.  May be empty if no connectors are configured.
    """
    required_types: List[str] = skill_config.get("required_tools", [])
    if not required_types:
        return []

    # Build a reverse map: type_str -> list of connector_ids
    type_to_ids: Dict[str, List[str]] = {}
    for connector_id, type_str in connector_manager._connector_types.items():
        type_to_ids.setdefault(type_str, []).append(connector_id)

    result: List["MCPToolPack"] = []
    for required_type in required_types:
        ids = type_to_ids.get(required_type, [])
        if not ids:
            logger.warning(
                "Required connector type '%s' not found among active connectors.",
                required_type,
            )
            continue
        for cid in ids:
            pack = connector_manager.get_connector_tools(cid)
            if pack is not None:
                result.append(pack)

    return result


def check_skill_connector_availability(
    skill_config: Dict[str, Any],
    connector_manager: "ConnectorManager",
) -> Dict[str, List[str]]:
    """Check which required connectors are available or missing.

    Args:
        skill_config (Dict[str, Any]): Skill configuration dict that may
            contain a ``required_tools`` key.
        connector_manager (ConnectorManager): The active connector
            manager instance.

    Returns:
        Dict[str, List[str]]: A dict with two keys:

        * ``"available"`` – connector types that have at least one
          active instance.
        * ``"missing"`` – connector types that have no active instance.
    """
    required_types: List[str] = skill_config.get("required_tools", [])
    active_types = set(connector_manager._connector_types.values())

    available: List[str] = []
    missing: List[str] = []
    for required_type in required_types:
        if required_type in active_types:
            available.append(required_type)
        else:
            missing.append(required_type)

    return {"available": available, "missing": missing}
