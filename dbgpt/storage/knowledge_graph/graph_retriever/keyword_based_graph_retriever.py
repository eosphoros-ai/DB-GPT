"""Keyword Based Graph Retriever."""

import logging
from typing import List, Tuple

from dbgpt.storage.graph_store.graph import Graph
from dbgpt.storage.knowledge_graph.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class KeywordBasedGraphRetriever(GraphRetrieverBase):
    """Keyword Based Graph Retriever class."""

    def __init__(self, graph_store_apdater, triplet_topk):
        """Initialize Keyword Based Graph Retriever."""
        self._graph_store_apdater = graph_store_apdater
        self._triplet_topk = triplet_topk

    async def retrieve(self, keywords: List[str]) -> Tuple[Graph, str]:
        """Retrieve from triplets graph with keywords."""
        subgraph = self._graph_store_apdater.explore_trigraph(
            subs=keywords,
            limit=self._triplet_topk,
        )

        return subgraph
