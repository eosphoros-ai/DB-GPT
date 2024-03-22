"""DBSchema retriever."""
from functools import reduce
from typing import List, Optional, cast

from dbgpt.core import Chunk
from dbgpt.datasource.base import BaseConnector
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.retriever.rerank import DefaultRanker, Ranker
from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.chat_util import run_async_tasks


class DBSchemaRetriever(BaseRetriever):
    """DBSchema retriever."""

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        top_k: int = 4,
        connector: Optional[BaseConnector] = None,
        query_rewrite: bool = False,
        rerank: Optional[Ranker] = None,
        **kwargs
    ):
        """Create DBSchemaRetriever.

        Args:
            vector_store_connector (VectorStoreConnector): vector store connector
            top_k (int): top k
            connector (Optional[BaseConnector]): RDBMSConnector.
            query_rewrite (bool): query rewrite
            rerank (Ranker): rerank

        Examples:
            .. code-block:: python

                from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
                from dbgpt.serve.rag.assembler.db_schema import DBSchemaAssembler
                from dbgpt.storage.vector_store.connector import VectorStoreConnector
                from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
                from dbgpt.rag.retriever.embedding import EmbeddingRetriever


                def _create_temporary_connection():
                    connect = SQLiteTempConnector.create_temporary_db()
                    connect.create_temp_tables(
                        {
                            "user": {
                                "columns": {
                                    "id": "INTEGER PRIMARY KEY",
                                    "name": "TEXT",
                                    "age": "INTEGER",
                                },
                                "data": [
                                    (1, "Tom", 10),
                                    (2, "Jerry", 16),
                                    (3, "Jack", 18),
                                    (4, "Alice", 20),
                                    (5, "Bob", 22),
                                ],
                            }
                        }
                    )
                    return connect


                connector = _create_temporary_connection()
                vector_store_config = ChromaVectorConfig(name="vector_store_name")
                embedding_model_path = "{your_embedding_model_path}"
                embedding_fn = embedding_factory.create(model_name=embedding_model_path)
                vector_connector = VectorStoreConnector.from_default(
                    "Chroma",
                    vector_store_config=vector_store_config,
                    embedding_fn=embedding_fn,
                )
                # get db struct retriever
                retriever = DBSchemaRetriever(
                    top_k=3,
                    vector_store_connector=vector_connector,
                    connector=connector,
                )
                chunks = retriever.retrieve("show columns from table")
                result = [chunk.content for chunk in chunks]
                print(f"db struct rag example results:{result}")
        """
        self._top_k = top_k
        self._connector = connector
        self._query_rewrite = query_rewrite
        self._vector_store_connector = vector_store_connector
        self._need_embeddings = False
        if self._vector_store_connector:
            self._need_embeddings = True
        self._rerank = rerank or DefaultRanker(self._top_k)

    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text

        Returns:
            List[Chunk]: list of chunks
        """
        if self._need_embeddings:
            queries = [query]
            candidates = [
                self._vector_store_connector.similar_search(query, self._top_k)
                for query in queries
            ]
            return cast(List[Chunk], reduce(lambda x, y: x + y, candidates))
        else:
            if not self._connector:
                raise RuntimeError("RDBMSConnector connection is required.")
            table_summaries = _parse_db_summary(self._connector)
            return [Chunk(content=table_summary) for table_summary in table_summaries]

    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Returns:
            List[Chunk]: list of chunks
        """
        return self._retrieve(query)

    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text

        Returns:
            List[Chunk]: list of chunks
        """
        if self._need_embeddings:
            queries = [query]
            candidates = [self._similarity_search(query) for query in queries]
            result_candidates = await run_async_tasks(
                tasks=candidates, concurrency_limit=1
            )
            return result_candidates
        else:
            from dbgpt.rag.summary.rdbms_db_summary import (  # noqa: F401
                _parse_db_summary,
            )

            table_summaries = await run_async_tasks(
                tasks=[self._aparse_db_summary()], concurrency_limit=1
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

    async def _aparse_db_summary(self) -> List[str]:
        """Similar search."""
        from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary

        if not self._connector:
            raise RuntimeError("RDBMSConnector connection is required.")
        return _parse_db_summary(self._connector)
