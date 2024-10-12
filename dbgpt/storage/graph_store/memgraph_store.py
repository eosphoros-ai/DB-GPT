"""Memory graph store."""

import logging
from typing import Generator

from dbgpt._private.pydantic import ConfigDict
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Graph, MemoryGraph

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

    def query(self, query: str, **args) -> Graph:
        """Execute a query on graph."""
        raise NotImplementedError("Query memory graph not allowed")

    def stream_query(self, query: str) -> Generator[Graph, None, None]:
        """Execute stream query."""
        raise NotImplementedError("Stream query memory graph not allowed")
