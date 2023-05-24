from pilot.vector_store.chroma_store import ChromaStore
from pilot.vector_store.milvus_store import MilvusStore

connector = {"Chroma": ChromaStore, "Milvus": MilvusStore}


class VectorStoreConnector:
    """vector store connector, can connect different vector db provided load document api and similar search api"""

    def __init__(self, vector_store_type, ctx: {}) -> None:
        self.ctx = ctx
        self.connector_class = connector[vector_store_type]
        self.client = self.connector_class(ctx)

    def load_document(self, docs):
        self.client.load_document(docs)

    def similar_search(self, docs, topk):
        return self.client.similar_search(docs, topk)
