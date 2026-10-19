"""Connector registry + three-layer plugin discovery.

1. entry-points group ``dbgpt.knowledge_sources`` (pip-installable plugins)
2. config-declared extra modules (``[rag.knowledge_source] extra_connector_modules``;
   modules that use ``@register_source_connector`` at import time)
3. in-process ``@register_source_connector`` (tests / notebooks)

Registration validates contract essentials early (unique type, meta present)
so a broken third-party connector fails loudly at startup, not mid-sync.
"""

from __future__ import annotations

import logging
from importlib import import_module, metadata
from typing import Dict, List, Optional, Type

from .base import BaseKnowledgeSourceConnector, ConnectorError, ConnectorMeta

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "dbgpt.knowledge_sources"


class ConnectorRegistry:
    _connectors: Dict[str, Type[BaseKnowledgeSourceConnector]] = {}

    @classmethod
    def register(cls, connector_cls: Type[BaseKnowledgeSourceConnector]) -> None:
        ctype = getattr(connector_cls, "type", "")
        if not ctype:
            raise ConnectorError(
                f"{connector_cls.__name__} must define a non-empty `type`"
            )
        existing = cls._connectors.get(ctype)
        if existing is connector_cls:
            return
        if existing is not None:
            raise ConnectorError(
                f"duplicate connector type '{ctype}' from both "
                f"{existing.__module__}.{existing.__name__} and "
                f"{connector_cls.__module__}.{connector_cls.__name__}"
            )
        meta = getattr(connector_cls, "meta", None)
        if not isinstance(meta, ConnectorMeta) or not meta.name:
            raise ConnectorError(
                f"connector '{ctype}' must declare meta = ConnectorMeta(name=...)"
            )
        cls._connectors[ctype] = connector_cls
        logger.info(f"registered datasource connector: {ctype}")

    @classmethod
    def get(cls, ctype: str) -> Optional[Type[BaseKnowledgeSourceConnector]]:
        return cls._connectors.get(ctype)

    @classmethod
    def all_types(cls) -> List[str]:
        return sorted(cls._connectors.keys())

    @classmethod
    def metas(cls) -> Dict[str, ConnectorMeta]:
        return {t: c.meta for t, c in sorted(cls._connectors.items())}

    @classmethod
    def clear(cls) -> None:
        """Test hook."""
        cls._connectors.clear()


def register_source_connector(connector_cls: Type[BaseKnowledgeSourceConnector]):
    """Decorator form of ``ConnectorRegistry.register``."""
    ConnectorRegistry.register(connector_cls)
    return connector_cls


def _connectors_from_entry_points() -> int:
    """Import pip plugins via the entry-points group. Returns count."""
    loaded = 0
    try:
        eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # py3.9 style: selectable() API
        eps = metadata.entry_points()
        eps = eps.select(group=ENTRY_POINT_GROUP) if hasattr(eps, "select") else []
    for ep in eps:
        try:
            connector_cls = ep.load()
        except Exception as exc:
            logger.error(f"failed to load datasource plugin '{ep.name}': {exc}")
            continue
        ConnectorRegistry.register(connector_cls)
        loaded += 1
    return loaded


def _connectors_from_modules(module_names: List[str]) -> int:
    """Import config-declared modules that self-register via decorator."""
    loaded = 0
    for name in module_names or []:
        try:
            import_module(name)
            loaded += 1
        except Exception as exc:
            logger.error(f"failed to import connector module '{name}': {exc}")
    return loaded


def load_builtin_connectors() -> int:
    """Register connectors shipped with dbgpt-ext."""
    try:
        import_module("dbgpt_ext.knowledge_source.connectors")
        return len(ConnectorRegistry.all_types())
    except Exception as exc:
        logger.error(f"failed to load builtin datasource connectors: {exc}")
        return 0


def ensure_source_connectors_loaded(
    extra_modules: Optional[List[str]] = None, once: bool = True
) -> List[str]:
    """Idempotent startup loader: built-ins → entry-points → extra modules.

    once=True keeps it cheap when called from several lifecycle hooks.
    """
    global _loaded
    if once and _loaded:
        return ConnectorRegistry.all_types()
    load_builtin_connectors()
    _connectors_from_entry_points()
    _connectors_from_modules(extra_modules or [])
    _loaded = True
    return ConnectorRegistry.all_types()


_loaded = False


def get_source_connector(ctype: str) -> Type[BaseKnowledgeSourceConnector]:
    """Lookup or raise — used by the sync engine at sync time."""
    connector_cls = ConnectorRegistry.get(ctype)
    if connector_cls is None:
        raise ConnectorError(f"unknown connector type: {ctype}")
    return connector_cls


def list_source_connector_metas() -> Dict[str, ConnectorMeta]:
    return ConnectorRegistry.metas()
