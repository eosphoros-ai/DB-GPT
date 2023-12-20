from functools import reduce
from typing import List, Optional

from dbgpt.util.chat_util import run_async_tasks
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
        code example:
        .. code-block:: python
            >>> from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnect
            >>> from dbgpt.serve.rag.assembler.db_struct import DBStructAssembler
            >>> from dbgpt.storage.vector_store.connector import VectorStoreConnector
            >>> from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
            >>> from dbgpt.rag.retriever.embedding import EmbeddingRetriever

            def _create_temporary_connection():
                connect = SQLiteTempConnect.create_temporary_db()
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
            connection = _create_temporary_connection()
            vector_store_config = ChromaVectorConfig(name="vector_store_name")
            embedding_model_path = "{your_embedding_model_path}"
            embedding_fn = embedding_factory.create(
                model_name=embedding_model_path
            )
            vector_connector = VectorStoreConnector.from_default(
                "Chroma",
                vector_store_config=vector_store_config,
                embedding_fn=embedding_fn
            )
            # get db struct retriever
            retriever = DBStructRetriever(top_k=3, vector_store_connector=vector_connector)
            chunks = retriever.retrieve("show columns from table")
            print(f"db struct rag example results:{[chunk.content for chunk in chunks]}")
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

    async def _aparse_db_summary(self) -> List[Chunk]:
        """Similar search."""
        from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary

        return _parse_db_summary()
