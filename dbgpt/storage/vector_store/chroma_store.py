import os
import logging
from typing import Any

from chromadb.config import Settings
from chromadb import PersistentClient
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.configs.model_config import PILOT_PATH

logger = logging.getLogger(__name__)


class ChromaStore(VectorStoreBase):
    """chroma database"""

    def __init__(self, ctx: {}) -> None:
        from langchain.vectorstores import Chroma

        self.ctx = ctx
        chroma_path = ctx.get(
            "CHROMA_PERSIST_PATH",
            os.path.join(PILOT_PATH, "data"),
        )
        self.persist_dir = os.path.join(
            chroma_path, ctx["vector_store_name"] + ".vectordb"
        )
        self.embeddings = ctx.get("embeddings", None)
        chroma_settings = Settings(
            # chroma_db_impl="duckdb+parquet", => deprecated configuration of Chroma
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )
        client = PersistentClient(path=self.persist_dir, settings=chroma_settings)

        collection_metadata = {"hnsw:space": "cosine"}
        self.vector_store_client = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            # client_settings=chroma_settings,
            client=client,
            collection_metadata=collection_metadata,
        )

    def similar_search(self, text, topk, **kwargs: Any) -> None:
        logger.info("ChromaStore similar search")
        return self.vector_store_client.similarity_search(text, topk, **kwargs)

    def similar_search_with_scores(self, text, topk, score_threshold) -> None:
        """
        Chroma similar_search_with_score.
        Return docs and relevance scores in the range [0, 1].
        Args:
            text(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs,0 is dissimilar, 1 is most similar.
        """
        logger.info("ChromaStore similar search")
        docs_and_scores = (
            self.vector_store_client.similarity_search_with_relevance_scores(
                query=text, k=topk, score_threshold=score_threshold
            )
        )
        return docs_and_scores

    def vector_name_exists(self):
        logger.info(f"Check persist_dir: {self.persist_dir}")
        if not os.path.exists(self.persist_dir):
            return False
        files = os.listdir(self.persist_dir)
        # Skip default file: chroma.sqlite3
        files = list(filter(lambda f: f != "chroma.sqlite3", files))
        return len(files) > 0

    def load_document(self, documents):
        logger.info("ChromaStore load document")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = self.vector_store_client.add_texts(texts=texts, metadatas=metadatas)
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
