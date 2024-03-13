from abc import ABC
from typing import List, Optional
from operator import itemgetter

from dbgpt.rag.chunk import Chunk


class Ranker(ABC):
    """Base Ranker"""

    def __init__(self, topk: int, rank_fn: Optional[callable] = None) -> None:
        """
        abstract base ranker
        Args:
            topk: int
            rank_fn: Optional[callable]
        """
        self.topk = topk
        self.rank_fn = rank_fn

    def rank(self, candidates_with_scores: List) -> List[Chunk]:
        """rank algorithm implementation return topk documents by candidates similarity score
        Args:
            candidates_with_scores: List[Tuple]
            topk: int
        Return:
            List[Document]
        """

        pass

    def _filter(self, candidates_with_scores: List) -> List[Chunk]:
        """filter duplicate candidates documents"""
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
    """Default Ranker"""

    def __init__(self, topk: int, rank_fn: Optional[callable] = None):
        super().__init__(topk, rank_fn)

    def rank(self, candidates_with_scores: List[Chunk]) -> List[Chunk]:
        """Default rank algorithm implementation
        return topk documents by candidates similarity score
        Args:
            candidates_with_scores: List[Tuple]
        Return:
            List[Document]
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
    """RRF(Reciprocal Rank Fusion) Ranker"""

    def __init__(self, topk: int, rank_fn: Optional[callable] = None, weights=[0.5, 0.5],c=60):
        super().__init__(topk, rank_fn)
        self.weights = weights
        self.c = c

    def rank(self, candidates_with_scores: List[Chunk]) -> List[Chunk]:
        """RRF rank algorithm implementation
        This code implements an algorithm called Reciprocal Rank Fusion (RRF), is a method for combining multiple result sets with different relevance indicators into a single result set. RRF requires no tuning, and the different relevance indicators do not have to be related to each other to achieve high-quality results.
        RRF uses the following formula to determine the score for ranking each document:
        score = 0.0
        for q in queries:
            if d in result(q):
                score += 1.0 / ( k + rank( result(q), d ) )
        return score
        reference:https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
        """
        # it will be implemented soon when multi recall is implemented
        # Create a union of all unique documents in the input doc_lists
        all_documents = set()
        for doc_list in candidates_with_scores:
            for doc in doc_list:
                all_documents.add(doc)

        # Initialize the RRF score dictionary for each document
        rrf_score_dic = {doc: 0.0 for doc in all_documents}

        # Calculate RRF scores for each document
        for doc_list, weight in zip(candidates_with_scores, self.weights):
            for rank, doc in enumerate(doc_list, start=1):
                rrf_score = weight * (1 / (rank + self.c))
                rrf_score_dic[doc] += rrf_score

        # Sort documents by their RRF scores in descending order
        sorted_documents = sorted(rrf_score_dic.items(), key=itemgetter(1), reverse=True)
        data = [score for text, score in sorted_documents[:self.topk]]
        average = sum(data) / len(data)
        result = []
        for sorted_doc in sorted_documents[:self.topk]:
            text, score = sorted_doc

            print('rrrrrrrrffff',score,text.split(',')[0])
            node_with_score = Chunk(score=score, content=text)
            result.append(node_with_score)
        return result
