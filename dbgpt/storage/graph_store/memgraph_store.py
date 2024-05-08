"""Graph store base class."""
import logging
from typing import List, Tuple

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Graph, Edge, Direction, MemoryGraph

logger = logging.getLogger(__name__)


class MemoryGraphStore(GraphStoreBase):
    """Memory graph store."""

    EDGE_NAME_KEY = 'label'

    def __init__(self, graph: MemoryGraph = MemoryGraph()):
        self._graph = graph

    def insert_triplet(self, sub: str, rel: str, obj: str):
        self._graph.append_edge(Edge(sub, obj, **{self.EDGE_NAME_KEY: rel}))

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        subgraph = self._graph.bfs([sub])
        return [
            (e.get_prop(self.EDGE_NAME_KEY), e.tid) for e in subgraph.edges()
        ]

    def delete_triplet(self, sub: str, rel: str, obj: str):
        self._graph.del_edge(sub, obj, **{self.EDGE_NAME_KEY: rel})

    def get_schema(self, refresh: bool = False) -> str:
        # todo: add memory graph schema
        pass

    def explore(
        self,
        subs: List[str],
        direction: Direction = Direction.BOTH,
        depth_limit: int = None,
        fan_limit: int = None,
        result_limit: int = None
    ) -> MemoryGraph:
        return self._graph.bfs(
            subs,
            direction,
            depth_limit,
            fan_limit,
            result_limit
        )

    def query(self, query: str, **args) -> Graph:
        raise NotImplementedError("Query memory graph not allowed")
