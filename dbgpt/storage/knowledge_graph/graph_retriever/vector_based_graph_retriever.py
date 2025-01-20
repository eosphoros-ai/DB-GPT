"""Vector Based Graph Retriever."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import Field

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.rag.index.base import IndexStoreBase, IndexStoreConfig
from dbgpt.rag.transformer.text_embedder import TextEmbedder
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


class VectorBasedGraphRetriever(GraphRetrieverBase):
    """Vector Based Graph Retriever class."""

    def __init__(
        self,
        graph_store_apdater,
        triplet_topk,
        similarity_search_topk,
        similarity_search_score_threshold,
    ):
        self._graph_store_apdater = graph_store_apdater
        self._triplet_topk = triplet_topk
        self._similarity_search_topk = similarity_search_topk
        self._similarity_search_score_threshold = similarity_search_score_threshold

    async def retrieve(
        self, vectors: List[List[float]]
    ) -> MemoryGraph:
        """Retrieve from triplet graph with vectors."""

        subgraph = self._graph_store_apdater.explore_trigraph(
            subs=vectors,
            topk=self._similarity_search_topk,
            limit=self._triplet_topk,
            score_threshold=self._similarity_search_score_threshold,
        )

        return subgraph
