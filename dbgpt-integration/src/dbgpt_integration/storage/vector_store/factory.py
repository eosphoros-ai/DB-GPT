"""Vector store factory."""
import logging
from typing import Tuple, Type

from dbgpt.storage import vector_store
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for vector store."""

    @staticmethod
    def create(
        vector_store_type: str, vector_space_name: str, vector_store_configure=None
    ) -> VectorStoreBase:
        """Create a VectorStore instance.

        Args:
            - vector_store_type: vector store type Chroma, Milvus, etc.
            - vector_store_config: vector store config
        """
        store_cls, cfg_cls = VectorStoreFactory.__find_type(vector_store_type)

        try:
            config = cfg_cls()
            if vector_store_configure:
                vector_store_configure(vector_space_name, config)
            return store_cls(config)
        except Exception as e:
            logger.error("create vector store failed: %s", e)
            raise e

    @staticmethod
    def __find_type(vector_store_type: str) -> Tuple[Type, Type]:
        for t in vector_store.__vector_store__:
            if t.lower() == vector_store_type.lower():
                store_cls, cfg_cls = getattr(vector_store, t)
                if issubclass(store_cls, VectorStoreBase) and issubclass(
                    cfg_cls, VectorStoreConfig
                ):
                    return store_cls, cfg_cls
        raise Exception(f"Vector store {vector_store_type} not supported")
