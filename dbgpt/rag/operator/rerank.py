from typing import Any, Optional, List

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.task.base import IN
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.retriever.rerank import DefaultRanker
from dbgpt.rag.retriever.rewrite import QueryRewrite


class RerankOperator(MapOperator[Any, Any]):
    """The Rewrite Operator."""

    def __init__(
        self,
        topk: Optional[int] = 3,
        algorithm: Optional[str] = "default",
        rank_fn: Optional[callable] = None,
        **kwargs
    ):
        """Init the query rewrite operator.
        Args:
            topk (int): The number of the candidates.
            algorithm (Optional[str]): The rerank algorithm name.
            rank_fn (Optional[callable]): The rank function.
        """
        super().__init__(**kwargs)
        self._algorithm = algorithm
        self._rerank = DefaultRanker(
            topk=topk,
            rank_fn=rank_fn,
        )

    async def map(self, candidates_with_scores: IN) -> List[Chunk]:
        """rerank the candidates.
        Args:
            candidates_with_scores (IN): The candidates with scores.
        Returns:
            List[Chunk]: The reranked candidates.
        """
        return await self.blocking_func_to_async(
            self._rerank.rank, candidates_with_scores
        )
