from pilot.vector_store.chroma_store import ChromaStore

# from pilot.vector_store.milvus_store import MilvusStore

connector = {"Chroma": ChromaStore, "Milvus": None}


class VectorStoreConnector:
    """vector store connector, can connect different vector db provided load document api and similar search api."""

    def __init__(self, vector_store_type, ctx: {}) -> None:
        """initialize vector store connector."""
        self.ctx = ctx
        self.connector_class = connector[vector_store_type]
        self.client = self.connector_class(ctx)

    def load_document(self, docs):
        """load document in vector database."""
        self.client.load_document(docs)

    def similar_search(self, docs, topk):
        """similar search in vector database."""
        return self.client.similar_search(docs, topk)

    def vector_name_exists(self):
        """is vector store name exist."""
        return self.client.vector_name_exists()
