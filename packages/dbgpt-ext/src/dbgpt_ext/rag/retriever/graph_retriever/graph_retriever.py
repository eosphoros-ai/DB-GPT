"""Graph Retriever."""

import logging
import os
from typing import List, Tuple, Union

from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.rag.transformer.simple_intent_translator import SimpleIntentTranslator
from dbgpt.storage.graph_store.graph import Graph, MemoryGraph
from dbgpt_ext.rag.transformer.local_text2gql import LocalText2GQL
from dbgpt_ext.rag.transformer.text2gql import Text2GQL

from ...transformer.text_embedder import TextEmbedder
from .base import GraphRetrieverBase
from .document_graph_retriever import (
    DocumentGraphRetriever,
)
from .keyword_based_graph_retriever import (  # noqa: E501
    KeywordBasedGraphRetriever,
)
from .text_based_graph_retriever import (
    TextBasedGraphRetriever,
)
from .vector_based_graph_retriever import (
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
        self._triplet_graph_enabled = config.triplet_graph_enabled or (
            os.getenv("TRIPLET_GRAPH_ENABLED", "").lower() == "true"
        )
        self._document_graph_enabled = config.document_graph_enabled or (
            os.getenv("DOCUMENT_GRAPH_ENABLED", "").lower() == "true"
        )
        triplet_topk = int(
            config.extract_topk or os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE")
        )
        document_topk = int(
            config.knowledge_graph_chunk_search_top_size
            or os.getenv("KNOWLEDGE_GRAPH_CHUNK_SEARCH_TOP_SIZE")
        )
        llm_client = config.llm_client
        model_name = config.model_name
        self._enable_similarity_search = (
            graph_store_adapter.graph_store.enable_similarity_search
        )
        self._embedding_batch_size = int(
            config.knowledge_graph_embedding_batch_size
            or os.getenv("KNOWLEDGE_GRAPH_EMBEDDING_BATCH_SIZE")
        )
        similarity_search_topk = int(
            config.similarity_search_topk
            or os.getenv("KNOWLEDGE_GRAPH_SIMILARITY_SEARCH_TOP_SIZE")
        )
        similarity_search_score_threshold = float(
            config.extract_score_threshold
            or os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE")
        )
        self._enable_text_search = config.enable_text_search or (
            os.getenv("TEXT_SEARCH_ENABLED", "").lower() == "true"
        )
        text2gql_model_enabled = config.text2gql_model_enabled or (
            os.getenv("TEXT2GQL_MODEL_ENABLED", "").lower() == "true"
        )
        text2gql_model_name = config.text2gql_model_name or os.getenv(
            "TEXT2GQL_MODEL_NAME"
        )
        text2gql_model_enabled = (
            os.environ["TEXT2GQL_MODEL_ENABLED"].lower() == "true"
            if "TEXT2GQL_MODEL_ENABLED" in os.environ
            else config.text2gql_model_enabled
        )
        text2gql_model_name = os.getenv(
            "TEXT2GQL_MODEL_NAME",
            config.text2gql_model_name,
        )
        text2gql_model_enabled = (
            os.environ["TEXT2GQL_MODEL_ENABLED"].lower() == "true"
            if "TEXT2GQL_MODEL_ENABLED" in os.environ
            else config.text2gql_model_enabled
        )
        text2gql_model_name = os.getenv(
            "TEXT2GQL_MODEL_NAME",
            config.text2gql_model_name,
        )
        text2gql_model_enabled = (
            os.environ["TEXT2GQL_MODEL_ENABLED"].lower() == "true"
            if "TEXT2GQL_MODEL_ENABLED" in os.environ
            else config.text2gql_model_enabled
        )
        text2gql_model_name = os.getenv(
            "TEXT2GQL_MODEL_NAME",
            config.text2gql_model_name,
        )

        self._keyword_extractor = KeywordExtractor(llm_client, model_name)
        self._text_embedder = TextEmbedder(config.embedding_fn)

        intent_interpreter = SimpleIntentTranslator(llm_client, model_name)
        if text2gql_model_enabled:
            text2gql = LocalText2GQL(text2gql_model_name)
        else:
            text2gql = Text2GQL(llm_client, model_name)

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
            graph_store_adapter,
            triplet_topk,
            intent_interpreter,
            text2gql,
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
