"""Rerank module for RAG retriever."""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from dbgpt.core import Chunk

RANK_FUNC = Callable[[List[Chunk]], List[Chunk]]


class Ranker(ABC):
    """Base Ranker."""

    def __init__(self, topk: int, rank_fn: Optional[RANK_FUNC] = None) -> None:
        """Create abstract base ranker.

        Args:
            topk: int
            rank_fn: Optional[callable]
        """
        self.topk = topk
        self.rank_fn = rank_fn

    @abstractmethod
    def rank(self, candidates_with_scores: List) -> List[Chunk]:
        """Return top k chunks after ranker.

        Rank algorithm implementation return topk documents by candidates
        similarity score

        Args:
            candidates_with_scores: List[Tuple]
            topk: int

        Return:
            List[Document]
        """

    def _filter(self, candidates_with_scores: List) -> List[Chunk]:
        """Filter duplicate candidates documents."""
        candidates_with_scores = sorted(
            candidates_with_scores, key=lambda x: x.score, reverse=True
        )
        visited_docs = set()
        new_candidates = []
        for candidate_chunk in candidates_with_scores:
            if candidate_chunk.content not in visited_docs:
                new_candidates.append(candidate_chunk)
                visited_docs.add(candidate_chunk.content)
        return new_candidates


class DefaultRanker(Ranker):
    """Default Ranker."""

    def __init__(self, topk: int, rank_fn: Optional[RANK_FUNC] = None):
        """Create Default Ranker with topk and rank_fn."""
        super().__init__(topk, rank_fn)

    def rank(self, candidates_with_scores: List[Chunk]) -> List[Chunk]:
        """Return top k chunks after ranker.

        Return top k documents by candidates similarity score

        Args:
            candidates_with_scores: List[Tuple]

        Return:
            List[Chunk]: List of top k documents
        """
        candidates_with_scores = self._filter(candidates_with_scores)
        if self.rank_fn is not None:
            candidates_with_scores = self.rank_fn(candidates_with_scores)
        else:
            candidates_with_scores = sorted(
                candidates_with_scores, key=lambda x: x.score, reverse=True
            )
        return candidates_with_scores[: self.topk]


class RRFRanker(Ranker):
    """RRF(Reciprocal Rank Fusion) Ranker."""

    def __init__(self, topk: int, rank_fn: Optional[RANK_FUNC] = None):
        """RRF rank algorithm implementation."""
        super().__init__(topk, rank_fn)

    def rank(self, candidates_with_scores: List[Chunk]) -> List[Chunk]:
        """RRF rank algorithm implementation.

        This code implements an algorithm called Reciprocal Rank Fusion (RRF), is a
        method for combining multiple result sets with different relevance indicators
        into a single result set. RRF requires no tuning, and the different relevance
        indicators do not have to be related to each other to achieve high-quality
        results.

        RRF uses the following formula to determine the score for ranking each document:
        score = 0.0
        for q in queries:
            if d in result(q):
                score += 1.0 / ( k + rank( result(q), d ) )
        return score
        reference:https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
        """
        # it will be implemented soon when multi recall is implemented
        return candidates_with_scores
