from pilot.vector_store.chroma_store import ChromaStore

from pilot.vector_store.milvus_store import MilvusStore

connector = {"Chroma": ChromaStore, "Milvus": MilvusStore}


class VectorStoreConnector:
    """VectorStoreConnector, can connect different vector db provided load document api_v1 and similar search api_v1.
    1.load_document:knowledge document source into vector store.(Chroma, Milvus, Weaviate)
    2.similar_search: similarity search from vector_store
    how to use reference:https://db-gpt.readthedocs.io/en/latest/modules/vector.html
    how to integrate:https://db-gpt.readthedocs.io/en/latest/modules/vector/milvus/milvus.html

    """

    def __init__(self, vector_store_type, ctx: {}) -> None:
        """initialize vector store connector."""
        self.ctx = ctx
        self.connector_class = connector[vector_store_type]
        self.client = self.connector_class(ctx)

    def load_document(self, docs):
        """load document in vector database."""
        return self.client.load_document(docs)

    def similar_search(self, docs, topk):
        """similar search in vector database."""
        return self.client.similar_search(docs, topk)

    def vector_name_exists(self):
        """is vector store name exist."""
        return self.client.vector_name_exists()

    def delete_by_ids(self, ids):
        self.client.delete_by_ids(ids=ids)
