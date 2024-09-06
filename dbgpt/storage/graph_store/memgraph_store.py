"""Memory graph store."""
import json
import logging
from typing import Generator, List, Optional, Tuple

from dbgpt._private.pydantic import ConfigDict
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Direction, Edge, Graph, MemoryGraph

logger = logging.getLogger(__name__)


class MemoryGraphStoreConfig(GraphStoreConfig):
    """Memory graph store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MemoryGraphStore(GraphStoreBase):
    """Memory graph store."""

    def __init__(self, graph_store_config: MemoryGraphStoreConfig):
        """Initialize MemoryGraphStore with a memory graph."""
        self._graph_store_config = graph_store_config
        self._graph = MemoryGraph()

    def get_config(self):
        """Get the graph store config."""
        return self._graph_store_config

    def get_edge_type(self) -> str:
        """Get the edge type."""
        raise NotImplementedError("Memory graph store does not have edge type")

    def get_vertex_type(self) -> str:
        """Get the vertex type."""
        raise NotImplementedError("Memory graph store does not have vertex type")

    def insert_triplet(self, sub: str, rel: str, obj: str):
        """Insert a triplet into the graph."""
        self._graph.append_edge(Edge(sub, obj, rel))

    def insert_graph(self, graph: Graph):
        """Add graph."""
        for vertex in graph.vertices():
            self._graph.upsert_vertex(vertex)

        for edge in graph.edges():
            self._graph.append_edge(edge)

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        """Retrieve triplets originating from a subject."""
        subgraph = self.explore([sub], direct=Direction.OUT, depth=1)
        return [(e.name, e.tid) for e in subgraph.edges()]

    def delete_triplet(self, sub: str, rel: str, obj: str):
        """Delete a specific triplet from the graph."""
        self._graph.del_edges(sub, obj, rel)

    def truncate(self):
        """Truncate graph."""
        self._graph.truncate()

    def drop(self):
        """Drop graph."""
        self._graph = None

    def get_schema(self, refresh: bool = False) -> str:
        """Return the graph schema as a JSON string."""
        return json.dumps(self._graph.schema())

    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Return self."""
        if not limit:
            return self._graph

        subgraph = MemoryGraph()
        for count, edge in enumerate(self._graph.edges()):
            if count >= limit:
                break
            subgraph.upsert_vertex(self._graph.get_vertex(edge.sid))
            subgraph.upsert_vertex(self._graph.get_vertex(edge.tid))
            subgraph.append_edge(edge)
            count += 1
        return subgraph

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: Optional[int] = None,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        return self._graph.search(subs, direct, depth, fan, limit)

    def query(self, query: str, **args) -> Graph:
        """Execute a query on graph."""
        raise NotImplementedError("Query memory graph not allowed")

    def stream_query(self, query: str) -> Generator[Graph, None, None]:
        """Execute stream query."""
        raise NotImplementedError("Stream query memory graph not allowed")
