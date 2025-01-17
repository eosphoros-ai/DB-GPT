"""Graph Retriever."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Union

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
from dbgpt.storage.knowledge_graph.graph_retriever.document_graph_retriever import (
    DocumentGraphRetriever,
)
from dbgpt.storage.knowledge_graph.graph_retriever.keyword_based_graph_retriever import (
    KeywordBasedGraphRetriever,
)
from dbgpt.storage.knowledge_graph.graph_retriever.text_based_graph_retriever import (
    TextBasedGraphRetriever,
)
from dbgpt.storage.knowledge_graph.graph_retriever.vector_based_graph_retriever import (
    VectorBasedGraphRetriever,
)

logger = logging.getLogger(__name__)


class GraphRetriever(GraphRetrieverBase):
    """Graph retriever class."""

    def __init__(
        self,
        triplet_graph_enabled,
        document_graph_enabled,
        triplet_topk,
        document_topk,
        keyword_extractor,
        enable_similarity_search,
        embedding_fn,
        embedding_batch_size,
        similarity_search_topk,
        similarity_search_score_threshold,
        enable_text_search,
        llm_client,
        model_name,
        graph_store_apdater,
    ):
        self._triplet_graph_enabled = triplet_graph_enabled
        self._document_graph_enabled = document_graph_enabled
        self._keyword_extractor = keyword_extractor

        self._enable_similarity_search = enable_similarity_search
        self._text_embedder = TextEmbedder(embedding_fn)
        self._embedding_batch_size = embedding_batch_size

        self._enable_text_search = enable_text_search

        self._keyword_based_graph_retriever = KeywordBasedGraphRetriever(
            graph_store_apdater, triplet_topk
        )
        self._vector_based_graph_retriever = VectorBasedGraphRetriever(
            graph_store_apdater,
            triplet_topk,
            similarity_search_topk,
            similarity_search_score_threshold,
        )
        self._text_based_graph_retriever = TextBasedGraphRetriever(
            graph_store_apdater, triplet_topk, llm_client, model_name
        )
        self._document_graph_retriever = DocumentGraphRetriever(
            graph_store_apdater,
            document_topk,
            similarity_search_topk,
            similarity_search_score_threshold,
        )

    async def retrieve(self, text: str) -> tuple[MemoryGraph, MemoryGraph, str]:
        """Retrieve subgraph from triplet graph and document graph."""

        subgraph = MemoryGraph()
        subgraph_for_doc = MemoryGraph()
        text2gql_query = ""

        # Retrieve from triplet graph and document graph
        if self._enable_text_search:
            # Retrieve from knowledge graph with text.
            subgraph, text2gql_query = await self._text_based_graph_retriever.retrieve(text)

        if subgraph.vertex_count == 0 and subgraph.edge_count == 0:
            # if not enable text search or text search failed to retrieve subgraph

            # Using subs to transfer keywords or embeddings
            subs: Union[List[str], List[List[float]]]
            if self._enable_similarity_search:
                # Embedding the question
                vector = await self._text_embedder.embed(text)
                # Embedding the keywords
                vectors = await self._text_embedder.batch_embed(
                    keywords, batch_size=self._triplet_embedding_batch_size
                )
                # Using the embeddings of keywords and question
                vectors.append(vector)
                subs = vectors
            else:
                # Extract keywords from original question
                keywords: List[str] = await self._keyword_extractor.extract(text)
                subs = keywords

            if self._triplet_graph_enabled:
                # Retrieve from triplet graph
                if self._enable_similarity_search:
                    # Retrieve from triplet graph with vectors
                    subgraph = await self._vector_based_graph_retriever.retrieve(subs)
                else:
                    # Retrieve from triplet graph with keywords
                    subgraph = await self._keyword_based_graph_retriever.retrieve(subs)
            if self._document_graph_enabled:
                # Retrieve from document graph
                if subgraph.vertex_count == 0 and subgraph.edge_count == 0:
                    # If not enable triplet graph or failed to retrieve subgraph
                    # Using subs to retrieve from document graph
                    subgraph_for_doc = await self._document_graph_retriever.retrieve(subs=subs)
                else:
                    # If retrieve subgraph from triplet graph successfully
                    # Using the vids to search chunks and doc
                    keywords_for_document_graph = []
                    for vertex in subgraph.vertices():
                        keywords_for_document_graph.append(vertex.name)
                    subgraph_for_doc = await self._document_graph_retriever.retrieve(
                        keywords_for_document_graph=keywords_for_document_graph
                    )

        return subgraph, subgraph_for_doc, text2gql_query
