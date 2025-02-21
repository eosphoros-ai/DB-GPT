"""Time weighted retriever."""

import datetime
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.core import Chunk
from dbgpt.rag.retriever.rerank import Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.base import IndexStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters

from .embedding import EmbeddingRetriever


def _get_hours_passed(time: datetime.datetime, ref_time: datetime.datetime) -> float:
    """Get the hours passed between two datetime objects."""
    return (time - ref_time).total_seconds() / 3600


class TimeWeightedEmbeddingRetriever(EmbeddingRetriever):
    """Time weighted embedding retriever."""

    def __init__(
        self,
        index_store: IndexStoreBase,
        top_k: int = 100,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        decay_rate: float = 0.01,
    ):
        """Initialize TimeWeightedEmbeddingRetriever.

        Args:
            index_store (IndexStoreBase): vector store connector
            top_k (int): top k
            query_rewrite (Optional[QueryRewrite]): query rewrite
            rerank (Ranker): rerank
        """
        super().__init__(
            index_store=index_store,
            top_k=top_k,
            query_rewrite=query_rewrite,
            rerank=rerank,
        )
        self.memory_stream: List[Chunk] = []
        self.other_score_keys: List[str] = []
        self.decay_rate: float = decay_rate
        self.default_salience: Optional[float] = None
        self._top_k = top_k
        self._k = 4

    def load_document(self, chunks: List[Chunk], **kwargs: Dict[str, Any]) -> List[str]:
        """Load document in vector database.

        Args:
            - chunks: document chunks.
        Return chunk ids.
        """
        current_time: Optional[datetime.datetime] = kwargs.get("current_time")  # type: ignore # noqa
        if current_time is None:
            current_time = datetime.datetime.now()
        # Avoid mutating input documents
        dup_docs = [deepcopy(d) for d in chunks]
        for i, doc in enumerate(dup_docs):
            if doc.metadata.get("last_accessed_at") is None:
                doc.metadata["last_accessed_at"] = current_time
            if "created_at" not in doc.metadata:
                doc.metadata["created_at"] = current_time
            doc.metadata["buffer_idx"] = len(self.memory_stream) + i
        self.memory_stream.extend(dup_docs)
        return self._index_store.load_document(dup_docs)

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        current_time = datetime.datetime.now()
        docs_and_scores = {
            doc.metadata["buffer_idx"]: (doc, self.default_salience)
            for doc in self.memory_stream[-self._k :]
        }
        # If a doc is considered salient, update the salience score
        docs_and_scores.update(self.get_salient_docs(query))
        rescored_docs = [
            (doc, self._get_combined_score(doc, relevance, current_time))
            for doc, relevance in docs_and_scores.values()
        ]
        rescored_docs.sort(key=lambda x: x[1], reverse=True)
        result = []
        # Ensure frequently accessed memories aren't forgotten
        for doc, _ in rescored_docs[: self._k]:
            # TODO: Update vector store doc once `update` method is exposed.
            buffered_doc = self.memory_stream[doc.metadata["buffer_idx"]]
            buffered_doc.metadata["last_accessed_at"] = current_time
            result.append(buffered_doc)
        return result

    def _get_combined_score(
        self,
        chunk: Chunk,
        vector_relevance: Optional[float],
        current_time: datetime.datetime,
    ) -> float:
        """Return the combined score for a document."""
        hours_passed = _get_hours_passed(
            current_time,
            chunk.metadata["last_accessed_at"],
        )
        score = (1.0 - self.decay_rate) ** hours_passed
        for key in self.other_score_keys:
            if key in chunk.metadata:
                score += chunk.metadata[key]
        if vector_relevance is not None:
            score += vector_relevance
        return score

    def get_salient_docs(self, query: str) -> Dict[int, Tuple[Chunk, float]]:
        """Return documents that are salient to the query."""
        docs_and_scores: List[Chunk]
        docs_and_scores = self._index_store.similar_search_with_scores(
            query, topk=self._top_k, score_threshold=0
        )
        results = {}
        for ck in docs_and_scores:
            if "buffer_idx" in ck.metadata:
                buffer_idx = ck.metadata["buffer_idx"]
                doc = self.memory_stream[buffer_idx]
                results[buffer_idx] = (doc, ck.score)
        return results
