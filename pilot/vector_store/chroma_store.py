import os

from langchain.vectorstores import Chroma
from pilot.logs import logger
from pilot.vector_store.vector_store_base import VectorStoreBase


class ChromaStore(VectorStoreBase):
    """chroma database"""

    def __init__(self, ctx: {}) -> None:
        self.ctx = ctx
        self.embeddings = ctx["embeddings"]
        self.persist_dir = os.path.join(
            ctx["chroma_persist_path"], ctx["vector_store_name"] + ".vectordb"
        )
        self.vector_store_client = Chroma(
            persist_directory=self.persist_dir, embedding_function=self.embeddings
        )

    def similar_search(self, text, topk) -> None:
        logger.info("ChromaStore similar search")
        return self.vector_store_client.similarity_search(text, topk)

    def vector_name_exists(self):
        return (
            os.path.exists(self.persist_dir) and len(os.listdir(self.persist_dir)) > 0
        )

    def load_document(self, documents):
        logger.info("ChromaStore load document")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = self.vector_store_client.add_texts(texts=texts, metadatas=metadatas)
        self.vector_store_client.persist()
        return ids

    def delete_by_ids(self, ids):
        collection = self.vector_store_client._collection
        collection.delete(ids=ids)
