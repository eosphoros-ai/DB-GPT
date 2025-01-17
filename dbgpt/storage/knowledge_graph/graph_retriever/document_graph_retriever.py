"""Dcoument Based Graph Retriever."""

import logging
from typing import List, Union, Optional

from pydantic import Field

from dbgpt.storage.graph_store.graph import MemoryGraph
from dbgpt.storage.knowledge_graph.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class DocumentGraphRetriever(GraphRetrieverBase):
    """Document Graph retriever class."""

    def __init__(
        self,
        graph_store_apdater,
        document_topk,
        similarity_search_topk,
        similarity_search_score_threshold,
    ):
        self._graph_store_apdater = graph_store_apdater
        self._document_topk = document_topk
        self._similarity_search_topk = similarity_search_topk
        self._similarity_search_score_threshold = similarity_search_score_threshold
    
    async def retrieve(
        self, subs: Optional[Union[List[str], List[List[float]]]], keywords_for_document_graph: Optional[List[str]]
    ) -> MemoryGraph:
        """Retrieve from document graph."""

        if subs:
            # Using subs to search chunks
            # subs -> chunks -> doc
            subgraph_for_doc = self._graph_store_apdater.explore_docgraph_without_entities(
                subs=subs,
                topk=self._similarity_search_topk,
                score_threshold=self._similarity_search_score_threshold,
                limit=self._document_topk,
            )
        elif keywords_for_document_graph:
            # Using the vids to search chunks and doc
            # entities -> chunks -> doc
            subgraph_for_doc = self._graph_store_apdater.explore_docgraph_with_entities(
                subs=keywords_for_document_graph,
                topk=self._similarity_search_topk,
                score_threshold=self._similarity_search_score_threshold,
                limit=self._document_topk,
            )
        
        return subgraph_for_doc
