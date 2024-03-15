import logging
import math
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, List, Optional

from pydantic import BaseModel, Field

from dbgpt.rag.chunk import Chunk

logger = logging.getLogger(__name__)


class VectorStoreConfig(BaseModel):
    """Vector store config."""

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
    embedding_fn: Optional[Any] = Field(
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
    """base class for vector store database"""

    @abstractmethod
    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """load document in vector database.
        Args:
            - chunks: document chunks.
        Return:
            - ids: chunks ids.
        """
        pass

    def load_document_with_limit(
        self, chunks: List[Chunk], max_chunks_once_load: int = 10, max_threads: int = 1
    ) -> List[str]:
        """load document in vector database with limit.
        Args:
            chunks: document chunks.
            max_chunks_once_load: Max number of chunks to load at once.
            max_threads: Max number of threads to use.
        Return:
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
    def similar_search(self, text, topk) -> List[Chunk]:
        """similar search in vector database.
        Args:
            - text: query text
            - topk: topk
        Return:
            - chunks: chunks.
        """
        pass

    @abstractmethod
    def similar_search_with_scores(
        self, text, topk, score_threshold: float
    ) -> List[Chunk]:
        """similar search in vector database with scores.
        Args:
            - text: query text
            - topk: topk
            - score_threshold: score_threshold: Optional, a floating point value between 0 to 1
        Return:
            - chunks: chunks.
        """
        pass

    @abstractmethod
    def vector_name_exists(self) -> bool:
        """is vector store name exist."""
        return False

    @abstractmethod
    def delete_by_ids(self, ids):
        """delete vector by ids.
        Args:
            - ids: vector ids
        """

    @abstractmethod
    def delete_vector_name(self, vector_name):
        """delete vector name.
        Args:
            - vector_name: vector store name
        """
        pass

    def _normalization_vectors(self, vectors):
        """normalization vectors to scale[0,1]"""
        import numpy as np

        norm = np.linalg.norm(vectors)
        return vectors / norm

    def _default_relevance_score_fn(self, distance: float) -> float:
        """Return a similarity score on a scale [0, 1]."""
        return 1.0 - distance / math.sqrt(2)
