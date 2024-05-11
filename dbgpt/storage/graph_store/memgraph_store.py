"""Graph store base class."""
import json
import logging
from typing import List, Tuple

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Direction, Edge, Graph, MemoryGraph

logger = logging.getLogger(__name__)


class MemoryGraphStore(GraphStoreBase):
    """Memory graph store."""

    EDGE_NAME_KEY = "label"

    def __init__(self, graph: MemoryGraph = MemoryGraph(edge_label=EDGE_NAME_KEY)):
        """Initialize MemoryGraphStore with a memory graph."""
        self._graph = graph

    def insert_triplet(self, sub: str, rel: str, obj: str):
        """Insert a triplet into the graph."""
        self._graph.append_edge(Edge(sub, obj, **{self.EDGE_NAME_KEY: rel}))

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        """Retrieve triplets originating from a subject."""
        subgraph = self.explore([sub], direct=Direction.OUT, depth=1)
        return [(e.get_prop(self.EDGE_NAME_KEY), e.tid) for e in subgraph.edges()]

    def delete_triplet(self, sub: str, rel: str, obj: str):
        """Delete a specific triplet from the graph."""
        self._graph.del_edges(sub, obj, **{self.EDGE_NAME_KEY: rel})

    def get_schema(self, refresh: bool = False) -> str:
        """Return the graph schema as a JSON string."""
        return json.dumps(self._graph.schema())

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = None,
        fan: int = None,
        limit: int = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        return self._graph.search(subs, direct, depth, fan, limit)

    def query(self, query: str, **args) -> Graph:
        """Execute a query on graph."""
        raise NotImplementedError("Query memory graph not allowed")
