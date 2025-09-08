"""Index store base class."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util import BaseParameters
from dbgpt.util.executor_utils import blocking_func_to_async_no_executor

logger = logging.getLogger(__name__)


@dataclass
class IndexStoreConfig(BaseParameters):
    """Index store config."""

    def create_store(self, **kwargs) -> "IndexStoreBase":
        """Create a new index store from the config."""
        raise NotImplementedError("Current index store does not support create_store")


class IndexStoreBase(ABC):
    """Index store base class."""

    def __init__(
        self,
        executor: Optional[Executor] = None,
        max_chunks_once_load: Optional[int] = None,
        max_threads: Optional[int] = None,
    ):
        """Init index store."""
        self._executor = executor or ThreadPoolExecutor()
        self._max_chunks_once_load = max_chunks_once_load or 10
        self._max_threads = max_threads or 1

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
        self,
        chunks: List[Chunk],
        max_chunks_once_load: Optional[int] = None,
        max_threads: Optional[int] = None,
    ) -> List[str]:
        """Load document in index database with specified limit.

        Args:
            chunks(List[Chunk]): Document chunks.
            max_chunks_once_load(int): Max number of chunks to load at once.
            max_threads(int): Max number of threads to use.

        Return:
            List[str]: Chunk ids.
        """
        max_chunks_once_load = max_chunks_once_load or self._max_chunks_once_load
        max_threads = max_threads or self._max_threads
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
        self,
        chunks: List[Chunk],
        max_chunks_once_load: Optional[int] = None,
        max_threads: Optional[int] = None,
        file_id: Optional[str] = None,
    ) -> List[str]:
        """Load document in index database with specified limit.

        Args:
            chunks(List[Chunk]): Document chunks.
            max_chunks_once_load(int): Max number of chunks to load at once.
            max_threads(int): Max number of threads to use.

        Return:
            List[str]: Chunk ids.
        """
        max_chunks_once_load = max_chunks_once_load or self._max_chunks_once_load
        max_threads = max_threads or self._max_threads
        file_id = file_id or None
        chunk_groups = [
            chunks[i : i + max_chunks_once_load]
            for i in range(0, len(chunks), max_chunks_once_load)
        ]
        logger.info(
            f"Loading {len(chunks)} chunks in {len(chunk_groups)} groups with "
            f"{max_threads} threads."
        )
        tasks = []
        for chunk_group in chunk_groups:
            tasks.append(self.aload_document(chunk_group, file_id))

        results = await self._run_tasks_with_concurrency(tasks, max_threads)

        ids = []
        loaded_cnt = 0
        for idx, success_ids in enumerate(results):
            if isinstance(success_ids, Exception):
                raise RuntimeError(
                    f"Failed to load chunk group {idx + 1}: {str(success_ids)}"
                ) from success_ids
            ids.extend(success_ids)
            loaded_cnt += len(success_ids)
            logger.info(f"Loaded {loaded_cnt} chunks, total {len(chunks)} chunks.")

        return ids

    async def _run_tasks_with_concurrency(self, tasks, max_concurrent):
        results = []
        for i in range(0, len(tasks), max_concurrent):
            batch = tasks[i : i + max_concurrent]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
        return results

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

    def full_text_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Full text search in index database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.
            filters(Optional[MetadataFilters]): metadata filters.
        Return:
            List[Chunk]: The similar documents.
        """
        raise NotImplementedError(
            "Full text search is not supported in this index store."
        )

    async def afull_text_search(
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
        return await blocking_func_to_async_no_executor(
            self.full_text_search, text, topk, filters
        )

    def is_support_full_text_search(self) -> bool:
        """Support full text search.

        Return:
            bool: The similar documents.
        """
        logger.warning("Full text search is not supported in this index store.")
        return False
