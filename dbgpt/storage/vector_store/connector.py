from dbgpt.storage import vector_store
from dbgpt.storage.vector_store.base import VectorStoreBase

connector = {}


class VectorStoreConnector:
    """VectorStoreConnector, can connect different vector db provided load document api_v1 and similar search api_v1.
    1.load_document:knowledge document source into vector store.(Chroma, Milvus, Weaviate)
    2.similar_search: similarity search from vector_store

    """

    def __init__(self, vector_store_type, ctx: {}) -> None:
        """initialize vector store connector.
        Args:
            - vector_store_type: vector store type Milvus, Chroma, Weaviate
            - ctx: vector store config params.
        """
        self.ctx = ctx
        self._register()

        if self._match(vector_store_type):
            self.connector_class = connector.get(vector_store_type)
        else:
            raise Exception(f"Vector Type Not support. {0}", vector_store_type)

        print(self.connector_class)
        self.client = self.connector_class(ctx)

    def load_document(self, docs):
        """load document in vector database."""
        return self.client.load_document(docs)

    def similar_search(self, doc: str, topk: int):
        """similar search in vector database.
        Args:
           - doc: query text
           - topk: topk
        """
        return self.client.similar_search(doc, topk)

    def similar_search_with_scores(self, doc: str, topk: int, score_threshold: float):
        """
        similar_search_with_score in vector database..
        Return docs and relevance scores in the range [0, 1].
        Args:
            doc(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs,0 is dissimilar, 1 is most similar.
        """
        return self.client.similar_search_with_scores(doc, topk, score_threshold)

    def vector_name_exists(self):
        """is vector store name exist."""
        return self.client.vector_name_exists()

    def delete_vector_name(self, vector_name):
        """vector store delete
        Args:
            - vector_name: vector store name
        """
        return self.client.delete_vector_name(vector_name)

    def delete_by_ids(self, ids):
        """vector store delete by ids.
        Args:
            - ids: vector ids
        """
        return self.client.delete_by_ids(ids=ids)

    def _match(self, vector_store_type) -> bool:
        if connector.get(vector_store_type):
            return True
        else:
            return False

    def _register(self):
        for cls in vector_store.__all__:
            if issubclass(getattr(vector_store, cls), VectorStoreBase):
                _k, _v = cls, getattr(vector_store, cls)
                connector.update({_k: _v})
