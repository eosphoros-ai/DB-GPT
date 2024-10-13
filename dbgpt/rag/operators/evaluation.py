"""Evaluation operators."""
import asyncio
from typing import Any, List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import JoinOperator
from dbgpt.core.interface.evaluation import EvaluationMetric, EvaluationResult
from dbgpt.core.interface.llm import LLMClient


class RetrieverEvaluatorOperator(JoinOperator[List[EvaluationResult]]):
    """Evaluator for retriever."""

    def __init__(
        self,
        evaluation_metrics: List[EvaluationMetric],
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        """Create a new RetrieverEvaluatorOperator."""
        self.llm_client = llm_client
        self.evaluation_metrics = evaluation_metrics
        super().__init__(combine_function=self._do_evaluation, **kwargs)

    async def _do_evaluation(
        self,
        query: str,
        prediction: List[Chunk],
        contexts: List[str],
        raw_dataset: Any = None,
    ) -> List[EvaluationResult]:
        """Run evaluation.

        Args:
            query(str): The query string.
            prediction(List[Chunk]): The retrieved chunks from the retriever.
            contexts(List[str]): The contexts from dataset.
            raw_dataset(Any): The raw data(single row) from dataset.
        """
        if isinstance(contexts, str):
            contexts = [contexts]
        prediction_strs = [chunk.content for chunk in prediction]
        tasks = []
        for metric in self.evaluation_metrics:
            tasks.append(metric.compute(prediction_strs, contexts))
        task_results = await asyncio.gather(*tasks)
        results = []
        for result, metric in zip(task_results, self.evaluation_metrics):
            results.append(
                EvaluationResult(
                    query=query,
                    prediction=prediction,
                    score=result.score,
                    contexts=contexts,
                    passing=result.passing,
                    raw_dataset=raw_dataset,
                    metric_name=metric.name(),
                )
            )
        return results
