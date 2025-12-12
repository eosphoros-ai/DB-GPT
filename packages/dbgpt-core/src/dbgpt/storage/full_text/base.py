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

    def is_support_full_text_search(self) -> bool:
        # 重写，新增抽象类
        """Support full text search.

        Full text store should support full text search by default.

        Return:
            bool: True, full text stores always support full text search.
        """
        return True  # 全文检索存储类应该始终支持全文检索

    def full_text_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        # 重写，新增抽象类
        """Full text search.

        Args:
            text (str): The query text.
            topk (int): Number of results to return. Default is 10.

        Returns:
            List[Chunk]: Search results as chunks.
        """
        # 调用抽象方法 similar_search_with_scores，但可以忽略分数阈值
        # 或者子类需要实现具体的全文检索逻辑

        return self.similar_search_with_scores(
            text, topk, score_threshold=0.0, filters=filters
        )

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
