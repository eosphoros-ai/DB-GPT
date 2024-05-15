"""Neo4j vector store."""
import logging
from typing import List, Optional, Tuple

from dbgpt._private.pydantic import ConfigDict
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Direction, Graph, MemoryGraph

logger = logging.getLogger(__name__)


class Neo4jStoreConfig(GraphStoreConfig):
    """Neo4j store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Neo4jStore(GraphStoreBase):
    """Neo4j graph store."""

    # todo: add neo4j implementation

    def __init__(self, graph_store_config: Neo4jStoreConfig):
        """Initialize the Neo4jStore with connection details."""
        pass

    def insert_triplet(self, sub: str, rel: str, obj: str):
        """Insert triplets."""
        pass

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        """Get triplets."""
        return []

    def delete_triplet(self, sub: str, rel: str, obj: str):
        """Delete triplets."""
        pass

    def drop(self):
        """Drop graph."""
        pass

    def get_schema(self, refresh: bool = False) -> str:
        """Get schema."""
        return ""

    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Get full graph."""
        return MemoryGraph()

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: Optional[int] = None,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Graph:
        """Explore the graph from given subjects up to a depth."""
        return MemoryGraph()

    def query(self, query: str, **args) -> Graph:
        """Execute a query on graph."""
        return MemoryGraph()
