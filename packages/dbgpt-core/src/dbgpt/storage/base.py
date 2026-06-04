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
    async def aload_document(
        self, chunks: List[Chunk], file_id: Optional[str] = None
    ) -> List[str]:
        """Load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.
            file_id(Optional[str]): file id for document-level tracking.

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

    def _safe_load_group(self, chunk_group: List[Chunk]) -> List[str]:
        """Load a chunk group with per-chunk fallback on group-level failure.

        Embedding back-ends can fail for individual chunks (e.g. NaN values in
        FP16 quantized models, or context-length overruns on a few outlier
        rows). Without this wrapper, a single bad chunk in a 10-chunk group
        causes ``load_document`` to raise, which propagates up through
        ``load_document_with_limit`` and aborts the entire indexing job —
        leaving zero chunks committed even when 99% of inputs are valid.

        Strategy: try the group as a whole; on failure, retry each chunk
        individually so we lose only the genuinely-bad ones. Returns the ids
        of successfully-loaded chunks (possibly empty).
        """
        try:
            return self.load_document(chunk_group)
        except Exception as group_err:
            if len(chunk_group) <= 1:
                first_id = (
                    getattr(chunk_group[0], "chunk_id", "?") if chunk_group else "?"
                )
                logger.warning(
                    "Skipping chunk that failed to load: "
                    f"chunk_id={first_id} error={group_err}"
                )
                return []
            logger.warning(
                f"Group of {len(chunk_group)} chunks failed ({group_err}); "
                "falling back to per-chunk retry"
            )
            ids: List[str] = []
            for chunk in chunk_group:
                try:
                    ids.extend(self.load_document([chunk]))
                except Exception as chunk_err:
                    logger.warning(
                        "Skipping chunk that failed to load: "
                        f"chunk_id={getattr(chunk, 'chunk_id', '?')} "
                        f"error={chunk_err}"
                    )
            return ids

    async def _safe_aload_group(
        self, chunk_group: List[Chunk], file_id: Optional[str] = None
    ) -> List[str]:
        """Async counterpart of ``_safe_load_group``."""
        try:
            return await self.aload_document(chunk_group, file_id)
        except Exception as group_err:
            if len(chunk_group) <= 1:
                first_id = (
                    getattr(chunk_group[0], "chunk_id", "?") if chunk_group else "?"
                )
                logger.warning(
                    "Skipping chunk that failed to load: "
                    f"chunk_id={first_id} error={group_err}"
                )
                return []
            logger.warning(
                f"Group of {len(chunk_group)} chunks failed ({group_err}); "
                "falling back to per-chunk retry"
            )
            ids: List[str] = []
            for chunk in chunk_group:
                try:
                    ids.extend(await self.aload_document([chunk], file_id))
                except Exception as chunk_err:
                    logger.warning(
                        "Skipping chunk that failed to load: "
                        f"chunk_id={getattr(chunk, 'chunk_id', '?')} "
                        f"error={chunk_err}"
                    )
            return ids

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
            List[str]: Chunk ids of successfully-loaded chunks.

        Note:
            Individual chunks that fail to load (e.g. due to embedding back-end
            errors on outlier inputs) are skipped with a warning; this method
            no longer raises when a partial subset of chunks fails. Callers
            that need strict all-or-nothing semantics should call
            ``load_document`` directly.
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
        skipped_cnt = 0
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            tasks = []
            for chunk_group in chunk_groups:
                tasks.append(executor.submit(self._safe_load_group, chunk_group))
            for future, chunk_group in zip(tasks, chunk_groups):
                success_ids = future.result()
                ids.extend(success_ids)
                loaded_cnt += len(success_ids)
                skipped_cnt += len(chunk_group) - len(success_ids)
                logger.info(f"Loaded {loaded_cnt} chunks, total {len(chunks)} chunks.")
        elapsed = time.time() - start_time
        if skipped_cnt:
            logger.warning(
                f"Loaded {loaded_cnt}/{len(chunks)} chunks in {elapsed:.1f}s; "
                f"{skipped_cnt} chunk(s) skipped due to load errors."
            )
        else:
            logger.info(f"Loaded {len(chunks)} chunks in {elapsed:.1f} seconds")
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
            List[str]: Chunk ids of successfully-loaded chunks.

        Note:
            Individual chunks that fail to load are skipped with a warning;
            this method no longer raises when a partial subset of chunks
            fails (matching the sync ``load_document_with_limit`` behavior).
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
            tasks.append(self._safe_aload_group(chunk_group, file_id))

        results = await self._run_tasks_with_concurrency(tasks, max_threads)

        ids = []
        loaded_cnt = 0
        skipped_cnt = 0
        for idx, (result, chunk_group) in enumerate(zip(results, chunk_groups)):
            if isinstance(result, Exception):
                # _safe_aload_group already swallows per-chunk errors; an
                # exception here would be an unexpected internal failure.
                logger.error(
                    f"Unexpected exception loading chunk group {idx + 1}: {result}"
                )
                skipped_cnt += len(chunk_group)
                continue
            ids.extend(result)
            loaded_cnt += len(result)
            skipped_cnt += len(chunk_group) - len(result)
            logger.info(f"Loaded {loaded_cnt} chunks, total {len(chunks)} chunks.")

        if skipped_cnt:
            logger.warning(
                f"Loaded {loaded_cnt}/{len(chunks)} chunks; "
                f"{skipped_cnt} chunk(s) skipped due to load errors."
            )

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
