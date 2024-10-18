"""Graph store factory."""

import logging
from typing import Tuple, Type

from dbgpt.storage import graph_store
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig

logger = logging.getLogger(__name__)


class GraphStoreFactory:
    """Factory for graph store."""

    @staticmethod
    def create(graph_store_type: str, graph_store_configure=None) -> GraphStoreBase:
        """Create a GraphStore instance.

        Args:
            - graph_store_type: graph store type Memory, TuGraph, Neo4j
            - graph_store_config: graph store config
        """
        store_cls, cfg_cls = GraphStoreFactory.__find_type(graph_store_type)

        try:
            config = cfg_cls()
            if graph_store_configure:
                graph_store_configure(config)
            return store_cls(config)
        except Exception as e:
            logger.error("create graph store failed: %s", e)
            raise e

    @staticmethod
    def __find_type(graph_store_type: str) -> Tuple[Type, Type]:
        for t in graph_store.__all__:
            if t.lower() == graph_store_type.lower():
                store_cls, cfg_cls = getattr(graph_store, t)
                if issubclass(store_cls, GraphStoreBase) and issubclass(
                    cfg_cls, GraphStoreConfig
                ):
                    return store_cls, cfg_cls
        raise Exception(f"Graph store {graph_store_type} not supported")
