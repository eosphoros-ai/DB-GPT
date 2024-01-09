from typing import Any
import logging
from elasticsearch import Elasticsearch
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt._private.config import Config

logger = logging.getLogger(__name__)

CFG = Config()


class ElasticSearchStore(VectorStoreBase):
    """`Elasticsearch` vector store.

    To use this, you should have the ``elasticsearch`` python package installed.
    """

    def __init__(self, ctx: dict) -> None:
        """init elasticsearch storage"""

        self.ctx = ctx
        self.connection_string = ctx.get("connection_string", None)
        self.embeddings = ctx.get("embeddings", None)
        self.collection_name = ctx.get("vector_store_name", None)

        self.vector_store_client = Elasticsearch(
            host=[self.connection_string]
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

    def load_document(self, documents) -> None:
        return self.vector_store_client.from_documents(documents)

    def delete_vector_name(self, vector_name):
        return self.vector_store_client.delete_collection()

    def delete_by_ids(self, ids):
        return self.vector_store_client.delete(ids)
