"""Neo4j vector store."""
import logging
from typing import List, Tuple

from dbgpt._private.pydantic import ConfigDict
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Graph, Direction

logger = logging.getLogger(__name__)


class Neo4jStoreConfig(GraphStoreConfig):
    """Neo4j store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Neo4jStore(GraphStoreBase):
    """Neo4j graph store."""

    # todo: add neo4j implementation

    def __init__(self, graph_store_config: Neo4jStoreConfig):
        pass

    def insert_triplet(self, sub: str, rel: str, obj: str):
        pass

    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        pass

    def delete_triplet(self, sub: str, rel: str, obj: str):
        pass

    def drop(self):
        pass

    def get_schema(self, refresh: bool = False) -> str:
        pass

    def get_full_graph(self, limit=None) -> Graph:
        pass

    def explore(self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = None,
        fan: int = None,
        limit: int = None
    ) -> Graph:
        pass

    def query(self, query: str, **args) -> Graph:
        pass
