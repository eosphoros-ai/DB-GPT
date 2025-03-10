"""Keyword Based Graph Retriever."""

import logging
from typing import List, Tuple

from dbgpt.storage.graph_store.graph import Graph
from dbgpt_ext.rag.retriever.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class KeywordBasedGraphRetriever(GraphRetrieverBase):
    """Keyword Based Graph Retriever class."""

    def __init__(self, graph_store_adapter, triplet_topk):
        """Initialize Keyword Based Graph Retriever."""
        self._graph_store_adapter = graph_store_adapter
        self._triplet_topk = triplet_topk

    async def retrieve(self, keywords: List[str]) -> Tuple[Graph, str]:
        """Retrieve from triplets graph with keywords."""
        subgraph = self._graph_store_adapter.explore_trigraph(
            subs=keywords,
            limit=self._triplet_topk,
        )

        return subgraph
