from functools import reduce
from typing import List

from dbgpt._private.chat_util import run_async_tasks
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.retriever.rerank import Ranker, DefaultRanker
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class EmbeddingRetriever(BaseRetriever):
    """Embedding retriever."""

    def __init__(
        self,
        top_k: int = 4,
        query_rewrite: bool = False,
        rerank: Ranker = None,
        vector_store_connector: VectorStoreConnector = None,
        **kwargs
    ):
        """
        Args:
            top_k (int): top k
            query_rewrite (bool): query rewrite
            rerank (Ranker): rerank
            vector_store_connector (VectorStoreConnector): vector store connector
        """
        self._top_k = top_k
        self._query_rewrite = query_rewrite
        self._vector_store_connector = vector_store_connector
        self._rerank = rerank or DefaultRanker(self._top_k)

    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        """
        queries = [query]
        candidates = [
            self._vector_store_connector.similar_search(query, self._top_k)
            for query in queries
        ]
        candidates = reduce(lambda x, y: x + y, candidates)
        return candidates

    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
        queries = [query]
        candidates_with_score = [
            self._vector_store_connector.similar_search_with_scores(
                query, self._top_k, score_threshold
            )
            for query in queries
        ]
        candidates_with_score = reduce(lambda x, y: x + y, candidates_with_score)
        candidates_with_score = self._rerank.rank(candidates_with_score)
        return candidates_with_score

    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        """
        queries = [query]
        candidates = [self._similarity_search(query) for query in queries]
        candidates = await run_async_tasks(tasks=candidates, concurrency_limit=1)
        return candidates

    async def _aretrieve_with_score(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
        queries = [query]
        candidates_with_score = [
            self._similarity_search_with_score(query, score_threshold)
            for query in queries
        ]
        candidates_with_score = await run_async_tasks(
            tasks=candidates_with_score, concurrency_limit=1
        )
        candidates_with_score = reduce(lambda x, y: x + y, candidates_with_score)
        candidates_with_score = self._rerank.rank(candidates_with_score)
        return candidates_with_score

    async def _similarity_search(self, query) -> List[Chunk]:
        """Similar search."""
        return self._vector_store_connector.similar_search(
            query,
            self._top_k,
        )

    async def _similarity_search_with_score(self, query, score_threshold):
        """Similar search with score."""
        return self._vector_store_connector.similar_search_with_scores(
            query, self._top_k, score_threshold
        )
