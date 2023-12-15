from typing import Any, List
import logging

from pydantic import Field

from dbgpt.rag.chunk import Chunk
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig
from dbgpt._private.config import Config

logger = logging.getLogger(__name__)

CFG = Config()


class PGVectorConfig(VectorStoreConfig):
    """PG vector store config."""

    connection_string: str = Field(
        default=None,
        description="the connection string of vector store, if not set, will use the default connection string.",
    )


class PGVectorStore(VectorStoreBase):
    """`Postgres.PGVector` vector store.

    To use this, you should have the ``pgvector`` python package installed.
    """

    def __init__(self, vector_store_config: PGVectorConfig) -> None:
        """init pgvector storage"""

        from langchain.vectorstores import PGVector

        self.connection_string = vector_store_config.connection_string
        self.embeddings = vector_store_config.embedding_fn
        self.collection_name = vector_store_config.name

        self.vector_store_client = PGVector(
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
            connection_string=self.connection_string,
        )

    def similar_search(self, text, topk, **kwargs: Any) -> None:
        return self.vector_store_client.similarity_search(text, topk)

    def vector_name_exists(self):
        try:
            self.vector_store_client.create_collection()
            return True
        except Exception as e:
            logger.error("vector_name_exists error", e.message)
            return False

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        lc_documents = [Chunk.chunk2langchain(chunk) for chunk in chunks]
        return self.vector_store_client.from_documents(lc_documents)

    def delete_vector_name(self, vector_name):
        return self.vector_store_client.delete_collection()

    def delete_by_ids(self, ids):
        return self.vector_store_client.delete(ids)
