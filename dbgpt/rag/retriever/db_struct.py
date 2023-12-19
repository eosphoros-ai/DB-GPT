from functools import reduce
from typing import List, Optional

from dbgpt._private.chat_util import run_async_tasks
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.retriever.rerank import Ranker, DefaultRanker
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class DBStructRetriever(BaseRetriever):
    """DBStruct retriever."""

    def __init__(
        self,
        top_k: int = 4,
        connection: Optional[RDBMSDatabase] = None,
        is_embeddings: bool = True,
        query_rewrite: bool = False,
        rerank: Ranker = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs
    ):
        """
        Args:
            top_k (int): top k
            connection (Optional[RDBMSDatabase]): RDBMSDatabase connection.
            is_embeddings (bool): Whether to query by embeddings in the vector store, Defaults to True.
            query_rewrite (bool): query rewrite
            rerank (Ranker): rerank
            vector_store_connector (VectorStoreConnector): vector store connector
        """
        self._top_k = top_k
        self._is_embeddings = is_embeddings
        self._connection = connection
        self._query_rewrite = query_rewrite
        self._vector_store_connector = vector_store_connector
        self._rerank = rerank or DefaultRanker(self._top_k)

    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        """
        if self._is_embeddings:
            queries = [query]
            candidates = [
                self._vector_store_connector.similar_search(query, self._top_k)
                for query in queries
            ]
            candidates = reduce(lambda x, y: x + y, candidates)
            return candidates
        else:
            from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary

            table_summaries = _parse_db_summary(self._connection)
            return [Chunk(content=table_summary) for table_summary in table_summaries]

    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
        return self._retrieve(query)

    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        """
        if self._is_embeddings:
            queries = [query]
            candidates = [self._similarity_search(query) for query in queries]
            candidates = await run_async_tasks(tasks=candidates, concurrency_limit=1)
            return candidates
        else:
            from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary

            table_summaries = await run_async_tasks(
                tasks=[self._aparse_db_summary(self._connection)], concurrency_limit=1
            )
            return [Chunk(content=table_summary) for table_summary in table_summaries]

    async def _aretrieve_with_score(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
        return await self._aretrieve(query)

    async def _similarity_search(self, query) -> List[Chunk]:
        """Similar search."""
        return self._vector_store_connector.similar_search(
            query,
            self._top_k,
        )

    async def _aparse_db_summary(self, query) -> List[Chunk]:
        """Similar search."""
        from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary

        return _parse_db_summary(self._connection)
