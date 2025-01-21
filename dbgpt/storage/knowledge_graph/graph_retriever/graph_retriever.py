"""Graph Retriever."""

import logging
import os
from typing import List, Tuple, Union

from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.rag.transformer.text_embedder import TextEmbedder
from dbgpt.storage.graph_store.graph import Graph, MemoryGraph
from dbgpt.storage.knowledge_graph.graph_retriever.base import GraphRetrieverBase
from dbgpt.storage.knowledge_graph.graph_retriever.document_graph_retriever import (
    DocumentGraphRetriever,
)
from dbgpt.storage.knowledge_graph.graph_retriever.keyword_based_graph_retriever import (  # noqa: E501
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
    """Graph Retriever class."""

    def __init__(
        self,
        config,
        graph_store_adapter,
    ):
        """Initialize Graph Retriever."""
        self._triplet_graph_enabled = (
            os.environ["TRIPLET_GRAPH_ENABLED"].lower() == "true"
            if "TRIPLET_GRAPH_ENABLED" in os.environ
            else config.triplet_graph_enabled
        )
        self._document_graph_enabled = (
            os.environ["DOCUMENT_GRAPH_ENABLED"].lower() == "true"
            if "DOCUMENT_GRAPH_ENABLED" in os.environ
            else config.document_graph_enabled
        )
        triplet_topk = int(
            os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE", config.extract_topk)
        )
        document_topk = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_CHUNK_SEARCH_TOP_SIZE",
                config.knowledge_graph_chunk_search_top_size,
            )
        )
        llm_client = config.llm_client
        model_name = config.model_name
        self._enable_similarity_search = (
            graph_store_adapter.graph_store.enable_similarity_search
        )
        self._embedding_batch_size = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_EMBEDDING_BATCH_SIZE",
                config.knowledge_graph_embedding_batch_size,
            )
        )
        similarity_search_topk = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_SIMILARITY_SEARCH_TOP_SIZE",
                config.similarity_search_topk,
            )
        )
        similarity_search_score_threshold = float(
            os.getenv(
                "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE",
                config.extract_score_threshold,
            )
        )
        self._enable_text_search = (
            os.environ["TEXT_SEARCH_ENABLED"].lower() == "true"
            if "TEXT_SEARCH_ENABLED" in os.environ
            else config.enable_text_search
        )

        self._keyword_extractor = KeywordExtractor(llm_client, model_name)
        self._text_embedder = TextEmbedder(config.embedding_fn)

        self._keyword_based_graph_retriever = KeywordBasedGraphRetriever(
            graph_store_adapter, triplet_topk
        )
        self._vector_based_graph_retriever = VectorBasedGraphRetriever(
            graph_store_adapter,
            triplet_topk,
            similarity_search_topk,
            similarity_search_score_threshold,
        )
        self._text_based_graph_retriever = TextBasedGraphRetriever(
            graph_store_adapter, triplet_topk, llm_client, model_name
        )
        self._document_graph_retriever = DocumentGraphRetriever(
            graph_store_adapter,
            document_topk,
            similarity_search_topk,
            similarity_search_score_threshold,
        )

    async def retrieve(self, text: str) -> Tuple[Graph, Tuple[Graph, str]]:
        """Retrieve subgraph from triplet graph and document graph."""
        subgraph = MemoryGraph()
        subgraph_for_doc = MemoryGraph()
        text2gql_query = ""

        # Retrieve from triplet graph and document graph
        if self._enable_text_search:
            # Retrieve from knowledge graph with text.
            subgraph, text2gql_query = await self._text_based_graph_retriever.retrieve(
                text
            )

        # Extract keywords from original question
        keywords: List[str] = await self._keyword_extractor.extract(text)

        if subgraph.vertex_count == 0 and subgraph.edge_count == 0:
            # if not enable text search or text search failed to retrieve subgraph

            # Using subs to transfer keywords or embeddings
            subs: Union[List[str], List[List[float]]]

            if self._enable_similarity_search:
                # Embedding the question
                vector = await self._text_embedder.embed(text)
                # Embedding the keywords
                vectors = await self._text_embedder.batch_embed(
                    keywords, batch_size=self._embedding_batch_size
                )
                # Using the embeddings of keywords and question
                vectors.append(vector)
                # Using vectors as subs
                subs = vectors
                logger.info(
                    "Search subgraph with the following keywords and question's "
                    f"embedding vector:\n[KEYWORDS]:{keywords}\n[QUESTION]:{text}"
                )
            else:
                # Using keywords as subs
                subs = keywords
                logger.info(
                    "Search subgraph with the following keywords:\n"
                    f"[KEYWORDS]:{keywords}"
                )

            # If enable triplet graph
            if self._triplet_graph_enabled:
                # Retrieve from triplet graph
                if self._enable_similarity_search:
                    # Retrieve from triplet graph with vectors
                    subgraph = await self._vector_based_graph_retriever.retrieve(subs)
                else:
                    # Retrieve from triplet graph with keywords
                    subgraph = await self._keyword_based_graph_retriever.retrieve(subs)

            # If enable document graph
            if self._document_graph_enabled:
                # Retrieve from document graph
                # If not enable triplet graph or failed to retrieve subgraph
                if subgraph.vertex_count == 0 and subgraph.edge_count == 0:
                    # Using subs to retrieve from document graph
                    subgraph_for_doc = await self._document_graph_retriever.retrieve(
                        subs
                    )
                else:
                    # If retrieve subgraph from triplet graph successfully
                    # Using entities in subgraph to search chunks and doc
                    subgraph_for_doc = await self._document_graph_retriever.retrieve(
                        subgraph
                    )

        return subgraph, (subgraph_for_doc, text2gql_query)
