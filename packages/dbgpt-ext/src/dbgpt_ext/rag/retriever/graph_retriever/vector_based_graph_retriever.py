"""Vector Based Graph Retriever."""

import logging
from typing import List, Tuple

from dbgpt.storage.graph_store.graph import Graph
from dbgpt_ext.rag.retriever.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class VectorBasedGraphRetriever(GraphRetrieverBase):
    """Vector Based Graph Retriever class."""

    def __init__(
        self,
        graph_store_adapter,
        triplet_topk,
        similarity_search_topk,
        similarity_search_score_threshold,
    ):
        """Initialize Vector Based Graph Retriever."""
        self._graph_store_adapter = graph_store_adapter
        self._triplet_topk = triplet_topk
        self._similarity_search_topk = similarity_search_topk
        self._similarity_search_score_threshold = similarity_search_score_threshold

    async def retrieve(self, vectors: List[List[float]]) -> Tuple[Graph, None]:
        """Retrieve from triplet graph with vectors."""
        subgraph = self._graph_store_adapter.explore_trigraph(
            subs=vectors,
            topk=self._similarity_search_topk,
            limit=self._triplet_topk,
            score_threshold=self._similarity_search_score_threshold,
        )

        return subgraph
