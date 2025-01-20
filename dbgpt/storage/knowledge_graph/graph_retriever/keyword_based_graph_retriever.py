"""Keyword Based Graph Retriever."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import Field

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.rag.index.base import IndexStoreBase, IndexStoreConfig
from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)
from dbgpt.storage.knowledge_graph.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class KeywordBasedGraphRetriever(GraphRetrieverBase):
    """Keyword Based Graph Retriever class."""

    def __init__(self, graph_store_apdater, triplet_topk):
        self._graph_store_apdater = graph_store_apdater
        self._triplet_topk = triplet_topk

    async def retrieve(self, keywords: List[str]) -> MemoryGraph:
        """Retrieve from triplets graph with keywords."""

        subgraph = self._graph_store_apdater.explore_trigraph(
            subs=keywords,
            limit=self._triplet_topk,
        )

        return subgraph
