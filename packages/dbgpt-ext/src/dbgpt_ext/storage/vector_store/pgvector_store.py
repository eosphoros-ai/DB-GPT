"""Postgres vector store."""

import logging
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@register_resource(
    _("PGVector Config"),
    "pg_vector_config",
    category=ResourceCategory.VECTOR_STORE,
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Connection String"),
            "connection_string",
            str,
            description=_(
                "The connection string of vector store, if not set, will use "
                "the default connection string."
            ),
            optional=True,
            default=None,
        ),
    ],
    description="PG vector config.",
)
class PGVectorConfig(VectorStoreConfig):
    """PG vector store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection_string: str = Field(
        default=None,
        description="the connection string of vector store, if not set, will use the "
        "default connection string.",
    )


@register_resource(
    _("PG Vector Store"),
    "pg_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    description=_("PG vector store."),
    parameters=[
        Parameter.build_from(
            _("PG Config"),
            "vector_store_config",
            PGVectorConfig,
            description=_("the pg config of vector store."),
            optional=True,
            default=None,
        ),
    ],
)
class PGVectorStore(VectorStoreBase):
    """PG vector store.

    To use this, you should have the ``pgvector`` python package installed.
    """

    def __init__(self, vector_store_config: PGVectorConfig) -> None:
        """Create a PGVectorStore instance."""
        try:
            from langchain.vectorstores import PGVector  # mypy: ignore
        except ImportError:
            raise ImportError(
                "Please install the `langchain` package to use the PGVector."
            )
        super().__init__()
        self._vector_store_config = vector_store_config

        self.connection_string = vector_store_config.connection_string
        self.embeddings = vector_store_config.embedding_fn
        self.collection_name = vector_store_config.name

        self.vector_store_client = PGVector(
            embedding_function=self.embeddings,  # type: ignore
            collection_name=self.collection_name,
            connection_string=self.connection_string,
        )

    def get_config(self) -> PGVectorConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Perform similar search in PGVector."""
        return self.vector_store_client.similarity_search(text, topk, filters)

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
        self.vector_store_client.from_documents(lc_documents)  # type: ignore
        return [str(chunk.chunk_id) for chunk in lc_documents]

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
        delete_ids = ids.split(",")
        return self.vector_store_client.delete(delete_ids)
