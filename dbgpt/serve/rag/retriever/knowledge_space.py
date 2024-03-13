from typing import List, Optional

from dbgpt._private.config import Config
from dbgpt.component import ComponentType
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async

CFG = Config()


class KnowledgeSpaceRetriever(BaseRetriever):
    """Knowledge Space retriever."""

    def __init__(
        self,
        space_name: str = None,
        top_k: Optional[int] = 4,
    ):
        """
        Args:
            space_name (str): knowledge space name
            top_k (Optional[int]): top k
        """
        if space_name is None:
            raise ValueError("space_name is required")
        self._space_name = space_name
        self._top_k = top_k
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        config = VectorStoreConfig(name=self._space_name, embedding_fn=embedding_fn)
        self._vector_store_connector = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE,
            vector_store_config=config,
        )
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        Return:
            List[Chunk]: list of chunks
        """
        candidates = self._vector_store_connector.similar_search(
            doc=query, topk=self._top_k
        )
        return candidates

    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        Return:
            List[Chunk]: list of chunks with score
        """
        candidates_with_score = self._vector_store_connector.similar_search_with_scores(
            doc=query, topk=self._top_k, score_threshold=score_threshold
        )
        return candidates_with_score

    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        Return:
            List[Chunk]: list of chunks
        """
        candidates = await blocking_func_to_async(self._executor, self._retrieve, query)
        return candidates

    async def _aretrieve_with_score(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        Return:
            List[Chunk]: list of chunks with score
        """
        candidates_with_score = await blocking_func_to_async(
            self._executor, self._retrieve_with_score, query, score_threshold
        )
        return candidates_with_score
