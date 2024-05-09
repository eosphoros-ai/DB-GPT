"""Graph store base class."""
import json
import logging
from typing import List, Tuple

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Graph, Edge, Direction, MemoryGraph

logger = logging.getLogger(__name__)


class MemoryGraphStore(GraphStoreBase):
    """Memory graph store."""

    EDGE_NAME_KEY = 'label'

    def __init__(
        self,
        graph: MemoryGraph = MemoryGraph(edge_label=EDGE_NAME_KEY)
    ):
        self._graph = graph

    def insert_triplet(self, sub: str, rel: str, obj: str):
        self._graph.append_edge(Edge(sub, obj, **{self.EDGE_NAME_KEY: rel}))

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        subgraph = self.explore(
            [sub],
            direct=Direction.OUT,
            depth=1
        )
        return [
            (e.get_prop(self.EDGE_NAME_KEY), e.tid) for e in subgraph.edges()
        ]

    def delete_triplet(self, sub: str, rel: str, obj: str):
        self._graph.del_edges(sub, obj, **{self.EDGE_NAME_KEY: rel})

    def get_schema(self, refresh: bool = False) -> str:
        return json.dumps(self._graph.schema())

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = None,
        fan: int = None,
        limit: int = None
    ) -> MemoryGraph:
        return self._graph.search(subs, direct, depth, fan, limit)

    def query(self, query: str, **args) -> Graph:
        raise NotImplementedError("Query memory graph not allowed")
