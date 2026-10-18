"""Knowledge source connectors — external DOCUMENT platforms (SaaS wiki /
docs services: Feishu, Yuque, Notion, RSS, ...), NOT database connections.

Database datasources (MySQL / Postgres / Spark / ...) live in
``dbgpt_ext.datasource``; this package integrates *document platforms* into
knowledge spaces. Community developers implement ``BaseKnowledgeSourceConnector``
and register via:

- entry-points group ``dbgpt.knowledge_sources`` (pip-installable), or
- ``[rag.knowledge_source] extra_connector_modules`` (dev shortcut), or
- ``@register_source_connector`` in-process.
"""

from .base import (
    BaseKnowledgeSourceConnector,
    ConnectorError,
    ConnectorMeta,
    FetchedItem,
    ResourceInfo,
    SyncCursor,
)
from .registry import (
    ensure_source_connectors_loaded,
    get_source_connector,
    list_source_connector_metas,
    register_source_connector,
)

__all__ = [
    "BaseKnowledgeSourceConnector",
    "ConnectorError",
    "ConnectorMeta",
    "FetchedItem",
    "ResourceInfo",
    "SyncCursor",
    "ensure_source_connectors_loaded",
    "get_source_connector",
    "list_source_connector_metas",
    "register_source_connector",
]
