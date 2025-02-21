"""The Rerank Operator."""

from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import MapOperator
from dbgpt.rag.retriever.rerank import RANK_FUNC, DefaultRanker


class RerankOperator(MapOperator[List[Chunk], List[Chunk]]):
    """The Rewrite Operator."""

    def __init__(
        self,
        topk: int = 3,
        algorithm: str = "default",
        rank_fn: Optional[RANK_FUNC] = None,
        **kwargs,
    ):
        """Create a new RerankOperator.

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

    async def map(self, candidates_with_scores: List[Chunk]) -> List[Chunk]:
        """Rerank the candidates.

        Args:
            candidates_with_scores (List[Chunk]): The candidates with scores.
        Returns:
            List[Chunk]: The reranked candidates.
        """
        return await self.blocking_func_to_async(
            self._rerank.rank, candidates_with_scores
        )
