"""Vector store base class."""
import logging
import math
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import Chunk, Embeddings

logger = logging.getLogger(__name__)


class VectorStoreConfig(BaseModel):
    """Vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    name: str = Field(
        default="dbgpt_collection",
        description="The name of vector store, if not set, will use the default name.",
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description="The password of vector store, if not set, will use the default "
        "password.",
    )
    embedding_fn: Optional[Embeddings] = Field(
        default=None,
        description="The embedding function of vector store, if not set, will use the "
        "default embedding function.",
    )
    max_chunks_once_load: int = Field(
        default=10,
        description="The max number of chunks to load at once. If your document is "
        "large, you can set this value to a larger number to speed up the loading "
        "process. Default is 10.",
    )
    max_threads: int = Field(
        default=1,
        description="The max number of threads to use. Default is 1. If you set this "
        "bigger than 1, please make sure your vector store is thread-safe.",
    )


class VectorStoreBase(ABC):
    """Vector store base class."""

    @abstractmethod
    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """

    def load_document_with_limit(
        self, chunks: List[Chunk], max_chunks_once_load: int = 10, max_threads: int = 1
    ) -> List[str]:
        """Load document in vector database with specified limit.

        Args:
            chunks(List[Chunk]): Document chunks.
            max_chunks_once_load(int): Max number of chunks to load at once.
            max_threads(int): Max number of threads to use.

        Return:
            List[str]: Chunk ids.
        """
        # Group the chunks into chunks of size max_chunks
        chunk_groups = [
            chunks[i : i + max_chunks_once_load]
            for i in range(0, len(chunks), max_chunks_once_load)
        ]
        logger.info(
            f"Loading {len(chunks)} chunks in {len(chunk_groups)} groups with "
            f"{max_threads} threads."
        )
        ids = []
        loaded_cnt = 0
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            tasks = []
            for chunk_group in chunk_groups:
                tasks.append(executor.submit(self.load_document, chunk_group))
            for future in tasks:
                success_ids = future.result()
                ids.extend(success_ids)
                loaded_cnt += len(success_ids)
                logger.info(f"Loaded {loaded_cnt} chunks, total {len(chunks)} chunks.")
        logger.info(
            f"Loaded {len(chunks)} chunks in {time.time() - start_time} seconds"
        )
        return ids

    @abstractmethod
    def similar_search(self, text: str, topk: int) -> List[Chunk]:
        """Similar search in vector database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.

        Return:
            List[Chunk]: The similar documents.
        """
        pass

    @abstractmethod
    def similar_search_with_scores(
        self, text, topk, score_threshold: float
    ) -> List[Chunk]:
        """Similar search with scores in vector database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.
            score_threshold(int): score_threshold: Optional, a floating point value
                between 0 to 1
        Return:
            List[Chunk]: The similar documents.
        """

    @abstractmethod
    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        return False

    @abstractmethod
    def delete_by_ids(self, ids: str):
        """Delete vectors by ids.

        Args:
            ids(str): The ids of vectors to delete, separated by comma.
        """

    @abstractmethod
    def delete_vector_name(self, vector_name: str):
        """Delete vector by name.

        Args:
            vector_name(str): The name of vector to delete.
        """

    def _normalization_vectors(self, vectors):
        """Return L2-normalization vectors to scale[0,1].

        Normalization vectors to scale[0,1].
        """
        import numpy as np

        norm = np.linalg.norm(vectors)
        return vectors / norm

    def _default_relevance_score_fn(self, distance: float) -> float:
        """Return a similarity score on a scale [0, 1]."""
        return 1.0 - distance / math.sqrt(2)
