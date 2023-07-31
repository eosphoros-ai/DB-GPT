import os

from chromadb.config import Settings
from langchain.vectorstores import Chroma
from pilot.logs import logger
from pilot.vector_store.vector_store_base import VectorStoreBase


class ChromaStore(VectorStoreBase):
    """chroma database"""

    def __init__(self, ctx: {}) -> None:
        self.ctx = ctx
        self.embeddings = ctx.get("embeddings", None)
        self.persist_dir = os.path.join(
            ctx["chroma_persist_path"], ctx["vector_store_name"] + ".vectordb"
        )
        chroma_settings = Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )
        self.vector_store_client = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            client_settings=chroma_settings,
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

    def delete_vector_name(self, vector_name):
        logger.info(f"chroma vector_name:{vector_name} begin delete...")
        self.vector_store_client.delete_collection()
        self._clean_persist_folder()
        return True

    def delete_by_ids(self, ids):
        logger.info(f"begin delete chroma ids...")
        collection = self.vector_store_client._collection
        collection.delete(ids=ids)

    def _clean_persist_folder(self):
        for root, dirs, files in os.walk(self.persist_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.persist_dir)
