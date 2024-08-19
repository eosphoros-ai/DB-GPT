"""GraphExtractor class."""

import logging
import os
from typing import List, Optional

from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.storage.knowledge_graph.community_summary import (
    CommunitySummaryKnowledgeGraphConfig,
)
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.factory import VectorStoreFactory

logger = logging.getLogger(__name__)

GRAPH_EXTRACT_PT = (
    # Extract TEXT to Chunk Links / Triplets / Element Summaries
    "Given the HISTORY and TEXT provided below, extract knowledge in the form of:\n"
    "1. Triplets: (subject, predicate, object)\n"
    "2. Node descriptions: [node, description]\n"
    "3. Edge descriptions: (subject, predicate, object) - description\n"
    "\n"
    "Guidelines:\n"
    "- Extract as many relevant triplets, node descriptions, and edge descriptions as possible.\n"
    "- Use the HISTORY for context, but focus on extracting new information from the TEXT.\n"
    "- Avoid stopwords and common knowledge.\n"
    "- Generate synonyms or aliases for important concepts, considering capitalization, pluralization, and common expressions.\n"
    "- Provide descriptions that add context or clarify the relationships.\n"
    "\n"
    "Format:\n"
    "Triplets:\n"
    "(subject, predicate, object)\n"
    "...\n"
    "\n"
    "Node Descriptions:\n"
    "[node, description]\n"
    "...\n"
    "\n"
    "Edge Descriptions:\n"
    "(subject, predicate, object) - description\n"
    "...\n"
    "\n"
    "---------------------\n"
    "Example:\n"
    "HISTORY: Philz is a coffee shop chain. Berkeley is a city in California.\n"
    "TEXT: Philz Coffee was founded by Phil Jaber in Berkeley, California in 1978. Known for its unique blends, Philz has expanded to multiple locations across the United States.\n"
    "\n"
    "Triplets:\n"
    "(Philz Coffee, founded by, Phil Jaber)\n"
    "(Philz Coffee, founded in, Berkeley)\n"
    "(Philz Coffee, founded in, 1978)\n"
    "(Philz Coffee, known for, unique blends)\n"
    "(Philz Coffee, expanded to, multiple locations)\n"
    "\n"
    "Node Descriptions:\n"
    "[Philz Coffee, A coffee shop chain founded in Berkeley]\n"
    "[Phil Jaber, Founder of Philz Coffee]\n"
    "[Berkeley, City in California where Philz Coffee was founded]\n"
    "\n"
    "Edge Descriptions:\n"
    "(Philz Coffee, founded by, Phil Jaber) - Indicates the creator and origin of the coffee chain\n"
    "(Philz Coffee, founded in, Berkeley) - Specifies the location where the company started\n"
    "(Philz Coffee, known for, unique blends) - Highlights a distinguishing feature of the brand\n"
    "\n"
    "---------------------\n"
    "HISTORY: {history}\n"
    "TEXT: {text}\n"
    "RESULTS:\n"
)


class GraphExtractor(LLMExtractor):
    """GraphExtractor class."""

    VECTOR_SPACE_SUFFIX = "_CHUNK_HISTORY"

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: str,
        config: CommunitySummaryKnowledgeGraphConfig,
    ):
        """Initialize the GraphExtractor."""
        super().__init__(llm_client, model_name, GRAPH_EXTRACT_PT)

        self.__init_chunk_history(config)

    def __init_chunk_history(self, config):
        self._vector_store_type = os.getenv(
            "VECTOR_STORE_TYPE", config.vector_store_type
        )
        self._vector_space = config.name + self.VECTOR_SPACE_SUFFIX
        self._max_chunks_once_load = config.max_chunks_once_load
        self._max_threads = config.max_threads
        self._topk = os.getenv(
            "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE", config.extract_topk
        )
        self._score_threshold = os.getenv(
            "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE",
            config.extract_score_threshold,
        )

        def configure(cfg: VectorStoreConfig):
            cfg.name = self._vector_space
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password

        self._chunk_history = VectorStoreFactory.create(
            self._vector_store_type, configure
        )

    async def extract(self, text: str, limit: Optional[int] = None) -> List:
        # load similar chunks
        chunks = await self._chunk_history.asimilar_search_with_scores(
            text, self._topk, self._score_threshold
        )
        history = [chunk.content for chunk in chunks]
        context = "\n".join(history) if history else None

        try:
            # extract with chunk history
            return await super()._extract(text, context, limit)

        finally:
            # save chunk to history
            await self._chunk_history.aload_document_with_limit(
                [Chunk(content=text)], self._max_chunks_once_load, self._max_threads
            )

    def _parse_response(self, text: str, limit: Optional[int] = None) -> List:
        # todo: parse results here
        return []

    def clean(self):
        self._chunk_history.delete_vector_name(self._vector_space)
