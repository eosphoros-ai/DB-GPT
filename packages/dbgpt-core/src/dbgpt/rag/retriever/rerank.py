"""Rerank module for RAG retriever."""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from dbgpt.core import Chunk, RerankEmbeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.util.executor_utils import blocking_func_to_async_no_executor
from dbgpt.util.i18n_utils import _

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
    def rank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
        """Return top k chunks after ranker.

        Rank algorithm implementation return topk documents by candidates
        similarity score

        Args:
            candidates_with_scores: List[Tuple]
            query: Optional[str]
        Return:
            List[Chunk]
        """

    async def arank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
        """Return top k chunks after ranker.

        Rank algorithm implementation return topk documents by candidates
        similarity score

        Args:
            candidates_with_scores: List[Tuple]
            query: Optional[str]
        Return:
            List[Chunk]
        """
        return await blocking_func_to_async_no_executor(
            self.rank, candidates_with_scores, query
        )

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

    def _rerank_with_scores(
        self, candidates_with_scores: List[Chunk], rank_scores: List[float]
    ) -> List[Chunk]:
        """Rerank candidates with scores."""
        for candidate, score in zip(candidates_with_scores, rank_scores):
            candidate.score = float(score)

        new_candidates_with_scores = sorted(
            candidates_with_scores, key=lambda x: x.score, reverse=True
        )
        return new_candidates_with_scores


@register_resource(
    _("Default Ranker"),
    "default_ranker",
    category=ResourceCategory.RAG,
    description=_("Default ranker(Rank by score)."),
    parameters=[
        Parameter.build_from(
            _("Top k"),
            "topk",
            int,
            description=_("The number of top k documents."),
        ),
        # Parameter.build_from(
        #     _("Rank Function"),
        #     "rank_fn",
        #     RANK_FUNC,
        #     description=_("The rank function."),
        #     optional=True,
        #     default=None,
        # ),
    ],
)
class DefaultRanker(Ranker):
    """Default Ranker."""

    def __init__(
        self,
        topk: int = 4,
        rank_fn: Optional[RANK_FUNC] = None,
    ):
        """Create Default Ranker with topk and rank_fn."""
        super().__init__(topk, rank_fn)

    def rank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
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

    def __init__(
        self,
        topk: int = 4,
        rank_fn: Optional[RANK_FUNC] = None,
    ):
        """RRF rank algorithm implementation."""
        super().__init__(topk, rank_fn)

    def rank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
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


@register_resource(
    _("CrossEncoder Rerank"),
    "cross_encoder_ranker",
    category=ResourceCategory.RAG,
    description=_("CrossEncoder ranker."),
    parameters=[
        Parameter.build_from(
            _("Top k"),
            "topk",
            int,
            description=_("The number of top k documents."),
        ),
        Parameter.build_from(
            _("Rerank Model"),
            "model",
            str,
            description=_("rerank model name, e.g., 'BAAI/bge-reranker-base'."),
        ),
        Parameter.build_from(
            _("device"),
            "device",
            str,
            description=_("device name, e.g., 'cpu'."),
        ),
    ],
)
class CrossEncoderRanker(Ranker):
    """CrossEncoder Ranker."""

    def __init__(
        self,
        topk: int = 4,
        model: str = "BAAI/bge-reranker-base",
        device: str = "cpu",
        rank_fn: Optional[RANK_FUNC] = None,
    ):
        """Cross Encoder rank algorithm implementation.

        Args:
            topk: int - The number of top k documents.
            model: str - rerank model name, e.g., 'BAAI/bge-reranker-base'.
            device: str - device name, e.g., 'cpu'.
            rank_fn: Optional[callable] - The rank function.
        Refer: https://www.sbert.net/examples/applications/cross-encoder/README.html
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "please `pip install sentence-transformers`",
            )
        self._model = CrossEncoder(model, max_length=512, device=device)
        super().__init__(topk, rank_fn)

    def rank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
        """Cross Encoder rank algorithm implementation.

        Args:
            candidates_with_scores: List[Chunk], candidates with scores
            query: Optional[str], query text
        Returns:
            List[Chunk], reranked candidates
        """
        if len(candidates_with_scores) <= 1:
            return candidates_with_scores
        contents = [candidate.content for candidate in candidates_with_scores]
        query_content_pairs = [
            [
                query if query is not None else "",
                content if content is not None else "",
            ]
            for content in contents
        ]
        rank_scores = self._model.predict(sentences=query_content_pairs)

        for candidate, score in zip(candidates_with_scores, rank_scores):
            candidate.score = float(score)

        new_candidates_with_scores = sorted(
            candidates_with_scores, key=lambda x: x.score, reverse=True
        )
        return new_candidates_with_scores[: self.topk]


class RerankEmbeddingsRanker(Ranker):
    """Rerank Embeddings Ranker."""

    def __init__(
        self,
        rerank_embeddings: RerankEmbeddings,
        topk: int = 4,
        rank_fn: Optional[RANK_FUNC] = None,
    ):
        """Rerank Embeddings rank algorithm implementation."""
        self._model = rerank_embeddings
        super().__init__(topk, rank_fn)

    def rank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
        """Rerank Embeddings rank algorithm implementation.

        Args:
            candidates_with_scores: List[Chunk], candidates with scores
            query: Optional[str], query text
        Returns:
            List[Chunk], reranked candidates
        """
        if not candidates_with_scores or not query:
            return candidates_with_scores

        contents = [candidate.content for candidate in candidates_with_scores]
        rank_scores = self._model.predict(query, contents)
        new_candidates_with_scores = self._rerank_with_scores(
            candidates_with_scores, rank_scores
        )
        return new_candidates_with_scores[: self.topk]

    async def arank(
        self, candidates_with_scores: List[Chunk], query: Optional[str] = None
    ) -> List[Chunk]:
        """Rerank Embeddings rank algorithm implementation.

        Args:
            candidates_with_scores: List[Chunk], candidates with scores
            query: Optional[str], query text
        Returns:
            List[Chunk], reranked candidates
        """
        if not candidates_with_scores or not query:
            return candidates_with_scores

        contents = [candidate.content for candidate in candidates_with_scores]
        rank_scores = await self._model.apredict(query, contents)
        new_candidates_with_scores = self._rerank_with_scores(
            candidates_with_scores, rank_scores
        )
        return new_candidates_with_scores[: self.topk]


class RetrieverNameRanker(Ranker):
    """RetrieverName Ranker."""

    def __init__(self, topk: int, rank_fn: Optional[callable] = None):  # type: ignore # noqa
        super().__init__(topk, rank_fn)

    def rank(self, candidates: List[Chunk], query: Optional[str] = None) -> List[Chunk]:
        """Use Retriever NameRanker return candidates with retriever name in filter_retrievers.
        Args:
            candidates: List[Tuple]
            query: Optional[str]
        Return:
            List[Chunk]
        """  # noqa
        candidates_with_scores = [
            candidate
            for candidate in candidates
            if candidate.retriever in self.filter_retrievers
        ]
        return candidates_with_scores

    @property
    def filter_retrievers(self):
        """Filter retrievers."""
        return ["qa_retriever", "title_retriever"]
