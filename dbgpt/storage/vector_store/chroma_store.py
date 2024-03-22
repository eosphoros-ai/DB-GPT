"""Chroma vector store."""
import logging
import os
from typing import Any, List

from chromadb import PersistentClient
from chromadb.config import Settings

from dbgpt._private.pydantic import Field
from dbgpt.configs.model_config import PILOT_PATH

# TODO: Recycle dependency on rag and storage
from dbgpt.core import Chunk

from .base import VectorStoreBase, VectorStoreConfig

logger = logging.getLogger(__name__)


class ChromaVectorConfig(VectorStoreConfig):
    """Chroma vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    persist_path: str = Field(
        default=os.getenv("CHROMA_PERSIST_PATH", None),
        description="the persist path of vector store.",
    )
    collection_metadata: dict = Field(
        default=None,
        description="the index metadata of vector store, if not set, will use the "
        "default metadata.",
    )


class ChromaStore(VectorStoreBase):
    """Chroma vector store."""

    def __init__(self, vector_store_config: ChromaVectorConfig) -> None:
        """Create a ChromaStore instance."""
        from langchain.vectorstores import Chroma

        chroma_vector_config = vector_store_config.dict()
        chroma_path = chroma_vector_config.get(
            "persist_path", os.path.join(PILOT_PATH, "data")
        )
        self.persist_dir = os.path.join(
            chroma_path, vector_store_config.name + ".vectordb"
        )
        self.embeddings = vector_store_config.embedding_fn
        chroma_settings = Settings(
            # chroma_db_impl="duckdb+parquet", => deprecated configuration of Chroma
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )
        client = PersistentClient(path=self.persist_dir, settings=chroma_settings)

        collection_metadata = chroma_vector_config.get("collection_metadata") or {
            "hnsw:space": "cosine"
        }
        self.vector_store_client = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            # client_settings=chroma_settings,
            client=client,
            collection_metadata=collection_metadata,
        )

    def similar_search(self, text, topk, **kwargs: Any) -> List[Chunk]:
        """Search similar documents."""
        logger.info("ChromaStore similar search")
        lc_documents = self.vector_store_client.similarity_search(text, topk, **kwargs)
        return [
            Chunk(content=doc.page_content, metadata=doc.metadata)
            for doc in lc_documents
        ]

    def similar_search_with_scores(self, text, topk, score_threshold) -> List[Chunk]:
        """Search similar documents with scores.

        Chroma similar_search_with_score.
        Return docs and relevance scores in the range [0, 1].
        Args:
            text(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value
                between 0 to 1 to filter the resulting set of retrieved docs,0 is
                dissimilar, 1 is most similar.
        """
        logger.info("ChromaStore similar search with scores")
        docs_and_scores = (
            self.vector_store_client.similarity_search_with_relevance_scores(
                query=text, k=topk, score_threshold=score_threshold
            )
        )
        return [
            Chunk(content=doc.page_content, metadata=doc.metadata, score=score)
            for doc, score in docs_and_scores
        ]

    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        logger.info(f"Check persist_dir: {self.persist_dir}")
        if not os.path.exists(self.persist_dir):
            return False
        files = os.listdir(self.persist_dir)
        # Skip default file: chroma.sqlite3
        files = list(filter(lambda f: f != "chroma.sqlite3", files))
        return len(files) > 0

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document to vector store."""
        logger.info("ChromaStore load document")
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        ids = [chunk.chunk_id for chunk in chunks]
        self.vector_store_client.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return ids

    def delete_vector_name(self, vector_name: str):
        """Delete vector name."""
        logger.info(f"chroma vector_name:{vector_name} begin delete...")
        self.vector_store_client.delete_collection()
        self._clean_persist_folder()
        return True

    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        logger.info(f"begin delete chroma ids: {ids}")
        ids = ids.split(",")
        if len(ids) > 0:
            collection = self.vector_store_client._collection
            collection.delete(ids=ids)

    def _clean_persist_folder(self):
        for root, dirs, files in os.walk(self.persist_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.persist_dir)
