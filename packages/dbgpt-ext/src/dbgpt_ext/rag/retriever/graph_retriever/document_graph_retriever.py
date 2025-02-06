"""Dcoument Based Graph Retriever."""

import logging
from typing import List, Tuple, Union

from dbgpt.storage.graph_store.graph import Graph
from dbgpt_ext.rag.retriever.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class DocumentGraphRetriever(GraphRetrieverBase):
    """Document Graph retriever class."""

    def __init__(
        self,
        graph_store_adapter,
        document_topk,
        similarity_search_topk,
        similarity_search_score_threshold,
    ):
        """Initialize Document Graph Retriever."""
        self._graph_store_adapter = graph_store_adapter
        self._document_topk = document_topk
        self._similarity_search_topk = similarity_search_topk
        self._similarity_search_score_threshold = similarity_search_score_threshold

    async def retrieve(
        self, input: Union[Graph, List[str], List[List[float]]]
    ) -> Tuple[Graph, None]:
        """Retrieve from document graph."""
        # If retrieve subgraph from triplet graph successfully
        if isinstance(input, Graph):
            # Get entities' vids from triplet subgraph
            keywords_for_document_graph = []
            for vertex in input.vertices():
                keywords_for_document_graph.append(vertex.name)
            # Using the vids to search chunks and doc
            # entities -> chunks -> doc
            subgraph_for_doc = self._graph_store_adapter.explore_docgraph_with_entities(
                subs=keywords_for_document_graph,
                topk=self._similarity_search_topk,
                score_threshold=self._similarity_search_score_threshold,
                limit=self._document_topk,
            )
        else:
            # Using subs to search chunks
            # subs -> chunks -> doc
            subgraph_for_doc = (
                self._graph_store_adapter.explore_docgraph_without_entities(
                    subs=input,
                    topk=self._similarity_search_topk,
                    score_threshold=self._similarity_search_score_threshold,
                    limit=self._document_topk,
                )
            )

        return subgraph_for_doc
