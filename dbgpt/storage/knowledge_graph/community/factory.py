"""CommunityStoreAdapter factory."""
import logging

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.tugraph_store import TuGraphStore
from dbgpt.storage.knowledge_graph.community.base import CommunityStoreAdapter
from dbgpt.storage.knowledge_graph.community.tugraph_adapter import (
    TuGraphCommunityStoreAdapter,
)

logger = logging.getLogger(__name__)


class CommunityStoreAdapterFactory:
    """Factory for community store adapter."""

    @staticmethod
    def create(graph_store: GraphStoreBase) -> CommunityStoreAdapter:
        """Create a CommunityStoreAdapter instance.

        Args:
            - graph_store_type: graph store type Memory, TuGraph, Neo4j
        """
        if isinstance(graph_store, TuGraphStore):
            return TuGraphCommunityStoreAdapter(graph_store)
        else:
            raise Exception(
                "create community store adapter for %s failed",
                graph_store.__class__.__name__,
            )
