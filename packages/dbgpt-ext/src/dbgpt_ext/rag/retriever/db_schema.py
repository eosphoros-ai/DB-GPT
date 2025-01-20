"""DBSchema retriever."""

import logging
from typing import List, Optional

from dbgpt._private.config import Config
from dbgpt.core import Chunk
from dbgpt.datasource.base import BaseConnector
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.retriever.rerank import DefaultRanker, Ranker
from ..summary.rdbms_db_summary import _parse_db_summary
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilter, MetadataFilters
from dbgpt.util.chat_util import run_tasks
from dbgpt.util.executor_utils import blocking_func_to_async_no_executor

logger = logging.getLogger(__name__)

CFG = Config()


class DBSchemaRetriever(BaseRetriever):
    """DBSchema retriever."""

    def __init__(
        self,
        table_vector_store_connector: VectorStoreBase,
        field_vector_store_connector: VectorStoreBase = None,
        separator: str = "--table-field-separator--",
        top_k: int = 4,
        connector: Optional[BaseConnector] = None,
        query_rewrite: bool = False,
        rerank: Optional[Ranker] = None,
        **kwargs,
    ):
        """Create DBSchemaRetriever.

        Args:
            table_vector_store_connector: VectorStoreBase
                to load and retrieve table info.
            field_vector_store_connector: VectorStoreBase
                to load and retrieve field info.
            separator: field/table separator
            top_k (int): top k
            connector (Optional[BaseConnector]): RDBMSConnector.
            query_rewrite (bool): query rewrite
            rerank (Ranker): rerank

        Examples:
            .. code-block:: python

                from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
                from dbgpt_serve.rag.assembler.db_schema import DBSchemaAssembler
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
        self._separator = separator
        self._top_k = top_k
        self._connector = connector
        self._query_rewrite = query_rewrite
        self._table_vector_store_connector = table_vector_store_connector
        self._field_vector_store_connector = field_vector_store_connector
        self._need_embeddings = False
        if self._table_vector_store_connector:
            self._need_embeddings = True
        self._rerank = rerank or DefaultRanker(self._top_k)

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """
        if self._need_embeddings:
            return self._similarity_search(query, filters)
        else:
            table_summaries = _parse_db_summary(self._connector)
            return [Chunk(content=table_summary) for table_summary in table_summaries]

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """
        return self._retrieve(query, filters)

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """
        return await blocking_func_to_async_no_executor(
            func=self._retrieve,
            query=query,
            filters=filters,
        )

    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: metadata filters.
        """
        return await self._aretrieve(query, filters)

    def _retrieve_field(self, table_chunk: Chunk, query) -> Chunk:
        metadata = table_chunk.metadata
        metadata["part"] = "field"
        filters = [MetadataFilter(key=k, value=v) for k, v in metadata.items()]
        field_chunks = self._field_vector_store_connector.similar_search_with_scores(
            query, self._top_k, 0, MetadataFilters(filters=filters)
        )
        field_contents = [chunk.content for chunk in field_chunks]
        table_chunk.content += "\n" + self._separator + "\n" + "\n".join(field_contents)
        return table_chunk

    def _similarity_search(
        self, query, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Similar search."""
        table_chunks = self._table_vector_store_connector.similar_search_with_scores(
            query, self._top_k, 0, filters
        )

        not_sep_chunks = [
            chunk for chunk in table_chunks if not chunk.metadata.get("separated")
        ]
        separated_chunks = [
            chunk for chunk in table_chunks if chunk.metadata.get("separated")
        ]
        if not separated_chunks:
            return not_sep_chunks

        # Create tasks list
        tasks = [
            lambda c=chunk: self._retrieve_field(c, query) for chunk in separated_chunks
        ]
        # Run tasks concurrently
        separated_result = run_tasks(tasks, concurrency_limit=3)

        # Combine and return results
        return not_sep_chunks + separated_result
