from pilot.vector_store.chroma_store import ChromaStore
from pilot import vector_store
from pilot.vector_store.base import VectorStoreBase

connector = {"Chroma": ChromaStore}

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
        self._register()
         
        if self._match(vector_store_type):
            self.connector_class = connector.get(vector_store_type)
        else:
            raise Exception(f"Vector Type Not support. {0}", vector_store_type)
        
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

    def delete_vector_name(self, vector_name):
        """vector store delete"""
        return self.client.delete_vector_name(vector_name)

    def delete_by_ids(self, ids):
        """vector store delete by ids."""
        return self.client.delete_by_ids(ids=ids)

    def _match(self, vector_store_type) -> bool:
        if connector.get(vector_store_type):
            return True
        else:
            return False
    
    def _register(self):
        for cls in vector_store.__all__:
            if issubclass(getattr(vector_store, cls), VectorStoreBase):
                connector.update({cls, getattr(vector_store, cls)})