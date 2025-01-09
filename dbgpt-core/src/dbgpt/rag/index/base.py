"""Index store base class."""
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict
from dbgpt.core import Chunk, Embeddings
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import (
    blocking_func_to_async,
    blocking_func_to_async_no_executor,
)

logger = logging.getLogger(__name__)


class IndexStoreConfig(BaseModel):
    """Index store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(
        default="dbgpt_collection",
        description="The name of index store, if not set, will use the default name.",
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

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert to dict."""
        return model_to_dict(self, **kwargs)


class IndexStoreBase(ABC):
    """Index store base class."""

    def __init__(self, executor: Optional[Executor] = None):
        """Init index store."""
        self._executor = executor or ThreadPoolExecutor()

    @abstractmethod
    def get_config(self) -> IndexStoreConfig:
        """Get the index store config."""

    @abstractmethod
    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """

    @abstractmethod
    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """

    @abstractmethod
    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Similar search with scores in index database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.
            score_threshold(int): score_threshold: Optional, a floating point value
                between 0 to 1
            filters(Optional[MetadataFilters]): metadata filters.
        Return:
            List[Chunk]: The similar documents.
        """

    @abstractmethod
    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete docs.

        Args:
            ids(str): The vector ids to delete, separated by comma.
        """

    @abstractmethod
    def truncate(self) -> List[str]:
        """Truncate data by name."""

    @abstractmethod
    def delete_vector_name(self, index_name: str):
        """Delete index by name.

        Args:
            index_name(str): The name of index to delete.
        """

    def vector_name_exists(self) -> bool:
        """Whether name exists."""
        return True

    def load_document_with_limit(
        self, chunks: List[Chunk], max_chunks_once_load: int = 10, max_threads: int = 1
    ) -> List[str]:
        """Load document in index database with specified limit.

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

    async def aload_document_with_limit(
        self, chunks: List[Chunk], max_chunks_once_load: int = 10, max_threads: int = 1
    ) -> List[str]:
        """Load document in index database with specified limit.

        Args:
            chunks(List[Chunk]): Document chunks.
            max_chunks_once_load(int): Max number of chunks to load at once.
            max_threads(int): Max number of threads to use.

        Return:
            List[str]: Chunk ids.
        """
        return await blocking_func_to_async(
            self._executor,
            self.load_document_with_limit,
            chunks,
            max_chunks_once_load,
            max_threads,
        )

    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Similar search in index database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.
            filters(Optional[MetadataFilters]): metadata filters.
        Return:
            List[Chunk]: The similar documents.
        """
        return self.similar_search_with_scores(text, topk, 1.0, filters)

    async def asimilar_search(
        self,
        query: str,
        topk: int,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Async similar_search in vector database."""
        return await blocking_func_to_async_no_executor(
            self.similar_search, query, topk, filters
        )

    async def asimilar_search_with_scores(
        self,
        query: str,
        topk: int,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Async similar_search_with_score in vector database."""
        return await blocking_func_to_async_no_executor(
            self.similar_search_with_scores, query, topk, score_threshold, filters
        )
