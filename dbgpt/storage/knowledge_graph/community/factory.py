"""GraphStoreAdapter factory."""

import logging

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.tugraph_store import TuGraphStore
from dbgpt.storage.knowledge_graph.community.base import GraphStoreAdapter
from dbgpt.storage.knowledge_graph.community.tugraph_store_adapter import (
    TuGraphStoreAdapter,
)

logger = logging.getLogger(__name__)


class GraphStoreAdapterFactory:
    """Factory for community store adapter."""

    @staticmethod
    def create(graph_store: GraphStoreBase) -> GraphStoreAdapter:
        """Create a GraphStoreAdapter instance.

        Args:
            - graph_store_type: graph store type Memory, TuGraph, Neo4j
        """
        if isinstance(graph_store, TuGraphStore):
            return TuGraphStoreAdapter(graph_store)
        else:
            raise Exception(
                "create community store adapter for %s failed",
                graph_store.__class__.__name__,
            )
