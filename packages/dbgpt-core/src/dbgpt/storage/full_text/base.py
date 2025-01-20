"""Full text store base class."""

import logging
from abc import abstractmethod
from concurrent.futures import Executor
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.storage.base import IndexStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import blocking_func_to_async

logger = logging.getLogger(__name__)


class FullTextStoreBase(IndexStoreBase):
    """Graph store base class."""

    def __init__(self, executor: Optional[Executor] = None):
        """Initialize vector store."""
        super().__init__(executor)

    @abstractmethod
    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Async load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """
        return await blocking_func_to_async(self._executor, self.load_document, chunks)

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
        """

    @abstractmethod
    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete docs.

        Args:
            ids(str): The vector ids to delete, separated by comma.
        """

    def delete_vector_name(self, index_name: str):
        """Delete name."""

    def truncate(self) -> List[str]:
        """Truncate the collection."""
        raise NotImplementedError
