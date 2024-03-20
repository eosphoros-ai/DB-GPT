"""Postgres vector store."""
import logging
from typing import Any, List

from dbgpt._private.config import Config
from dbgpt._private.pydantic import Field
from dbgpt.core import Chunk
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig

logger = logging.getLogger(__name__)

CFG = Config()


class PGVectorConfig(VectorStoreConfig):
    """PG vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    connection_string: str = Field(
        default=None,
        description="the connection string of vector store, if not set, will use the "
        "default connection string.",
    )


class PGVectorStore(VectorStoreBase):
    """PG vector store.

    To use this, you should have the ``pgvector`` python package installed.
    """

    def __init__(self, vector_store_config: PGVectorConfig) -> None:
        """Create a PGVectorStore instance."""
        from langchain.vectorstores import PGVector

        self.connection_string = vector_store_config.connection_string
        self.embeddings = vector_store_config.embedding_fn
        self.collection_name = vector_store_config.name

        self.vector_store_client = PGVector(
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
            connection_string=self.connection_string,
        )

    def similar_search(self, text: str, topk: int, **kwargs: Any) -> List[Chunk]:
        """Perform similar search in PGVector."""
        return self.vector_store_client.similarity_search(text, topk)

    def vector_name_exists(self) -> bool:
        """Check if vector name exists."""
        try:
            self.vector_store_client.create_collection()
            return True
        except Exception as e:
            logger.error(f"vector_name_exists error, {str(e)}")
            return False

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document to PGVector.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """
        lc_documents = [Chunk.chunk2langchain(chunk) for chunk in chunks]
        return self.vector_store_client.from_documents(lc_documents)

    def delete_vector_name(self, vector_name: str):
        """Delete vector by name.

        Args:
            vector_name(str): vector name.
        """
        return self.vector_store_client.delete_collection()

    def delete_by_ids(self, ids: str):
        """Delete vector by ids.

        Args:
            ids(str): vector ids, separated by comma.
        """
        return self.vector_store_client.delete(ids)
