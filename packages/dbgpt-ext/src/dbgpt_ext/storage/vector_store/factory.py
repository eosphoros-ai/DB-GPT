"""Vector store factory."""

import logging
from typing import List, Optional, Tuple, Type

from dbgpt.core import Embeddings
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig
from dbgpt_ext.storage import __vector_store__ as vector_store_list
from dbgpt_ext.storage import _select_rag_storage

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for vector store."""

    @staticmethod
    def create(
        vector_store_type: str,
        vector_space_name: str,
        vector_store_configure=None,
        embedding_fn: Optional[Embeddings] = None,
        kwargs: Optional[dict] = None,
    ) -> VectorStoreBase:
        """Create a VectorStore instance.

        Args:
            - vector_store_type: vector store type Chroma, Milvus, etc.
            - vector_store_config: vector store config
        """
        store_cls, cfg_cls = VectorStoreFactory.__find_type(vector_store_type)
        kwargs = kwargs or {}
        try:
            # config = cfg_cls()
            # if vector_store_configure:
            #     vector_store_configure(vector_space_name, config)
            return store_cls(
                vector_store_config=vector_store_configure,
                name=vector_space_name,
                embedding_fn=embedding_fn,
                **kwargs,
            )
        except Exception as e:
            logger.error("create vector store failed: %s", e)
            raise e

    @staticmethod
    def __find_type(vector_store_type: str) -> Tuple[Type, Type]:
        for t in vector_store_list:
            if t.lower() == vector_store_type.lower():
                store_cls, cfg_cls = _select_rag_storage(t)
                if issubclass(store_cls, VectorStoreBase) and issubclass(
                    cfg_cls, VectorStoreConfig
                ):
                    return store_cls, cfg_cls
        raise Exception(f"Vector store {vector_store_type} not supported")

    @classmethod
    def get_all_supported_types(cls) -> List[str]:
        """Get all supported types."""
        support_types = []
        vector_store_classes = _get_all_subclasses()
        for vector_cls in vector_store_classes:
            support_types.append(vector_cls.__type__)
        return support_types


def _get_all_subclasses() -> List[Type[VectorStoreConfig]]:
    """Get all subclasses of cls."""

    return VectorStoreConfig.__subclasses__()
