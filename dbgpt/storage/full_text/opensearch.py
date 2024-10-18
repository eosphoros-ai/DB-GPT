"""OpenSearch index store."""

from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters


class OpenSearch(FullTextStoreBase):
    """OpenSearch index store."""

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """
        pass

    def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Async load document in index database.

        Args:
            chunks(List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """
        pass

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
        pass

    def delete_by_ids(self, ids: str):
        """Delete docs.

        Args:
            ids(str): The vector ids to delete, separated by comma.

        """
        pass

    def delete_vector_name(self, index_name: str):
        """Delete name."""
        pass
