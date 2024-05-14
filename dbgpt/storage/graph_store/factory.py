"""Connector for vector store."""
import logging
from typing import Optional, Type

from dbgpt.rag.index.base import IndexStoreConfig
from dbgpt.storage import graph_store
from dbgpt.storage.graph_store.base import GraphStoreBase

logger = logging.getLogger(__name__)


class GraphStoreFactory:
    """Factory for graph store."""

    @staticmethod
    def create(
        graph_store_type: str,
        graph_store_config: Optional[IndexStoreConfig] = None
    ) -> GraphStoreBase:
        """Create a GraphStore instance.

        Args:
            - graph_store_type: graph store type Memory, TuGraph, Neo4j
            - graph_store_config: graph store config
        """
        cls = GraphStoreFactory.__find_type(graph_store_type)

        try:
            return cls(graph_store_config)
        except Exception as e:
            logger.error("create graph store failed: %s", e)
            raise e

    @staticmethod
    def __find_type(graph_store_type: str) -> Type:
        for t in graph_store.__all__:
            if t.lower() == graph_store_type.lower():
                cls = getattr(graph_store, t)
                if issubclass(cls, GraphStoreBase):
                    return cls
        raise Exception(f"Graph store {graph_store_type} not supported")
