"""GraphExtractor class."""
import logging
import os
from typing import Optional, List

from dbgpt.core import LLMClient, Chunk
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.storage.knowledge_graph.community_summary import \
    CommunitySummaryKnowledgeGraphConfig
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.factory import VectorStoreFactory

logger = logging.getLogger(__name__)

GRAPH_EXTRACT_PT = (
    # TODO: provide prompt template here
    "Extract TEXT to Chunk Links / Triplets / Element Summaries "
    "based on HISTORY.\n"
    "Avoid stopwords.\n"
    "---------------------\n"
    "Example:\n"
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
        config: CommunitySummaryKnowledgeGraphConfig
    ):
        """Initialize the GraphExtractor."""
        super().__init__(llm_client, model_name, GRAPH_EXTRACT_PT)

        self.__init_chunk_history(config)

    def __init_chunk_history(self, config):
        self._vector_store_type = (
            os.getenv("VECTOR_STORE_TYPE") or config.vector_store_type
        )
        self._vector_space = config.name + self.VECTOR_SPACE_SUFFIX
        self._max_chunks_once_load = config.max_chunks_once_load
        self._max_threads = config.max_threads
        self._topk = (
            os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE")
            or config.extract_topk
        )
        self._score_threshold = (
            os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE")
            or config.extract_score_threshold
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
                [Chunk(content=text)],
                self._max_chunks_once_load,
                self._max_threads
            )

    def _parse_response(
        self, text: str, limit: Optional[int] = None
    ) -> List:
        # todo: parse results here
        return []

    def clean(self):
        self._chunk_history.delete_vector_name(self._vector_space)
