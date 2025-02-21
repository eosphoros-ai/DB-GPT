"""Evaluation for retriever."""

from abc import ABC
from typing import Any, Dict, List, Optional, Sequence, Type

from dbgpt.core import Embeddings, LLMClient
from dbgpt.core.interface.evaluation import (
    BaseEvaluationResult,
    DatasetType,
    EvaluationMetric,
    EvaluationResult,
    Evaluator,
)
from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.util.similarity_util import calculate_cosine_similarity

from ..operators.evaluation import RetrieverEvaluatorOperator


class RetrieverEvaluationMetric(EvaluationMetric[List[str], str], ABC):
    """Evaluation metric for retriever.

    The prediction is a list of str(content from chunks) and the context is a string.
    """


class RetrieverSimilarityMetric(RetrieverEvaluationMetric):
    """Similarity metric for retriever."""

    def __init__(self, embeddings: Embeddings):
        """Create a SimilarityMetric with embeddings."""
        self._embeddings = embeddings

    def sync_compute(
        self,
        prediction: List[str],
        contexts: Optional[Sequence[str]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric.

        Args:
            prediction(List[str]): The retrieved chunks from the retriever.
            contexts(Sequence[str]): The contexts from dataset.
            query:(Optional[str]) The query text.

        Returns:
            BaseEvaluationResult: The evaluation result.
                The score is the mean of the cosine similarity between the prediction
                and the contexts.
        """
        if not prediction or not contexts:
            return BaseEvaluationResult(
                prediction=prediction,
                contexts=contexts,
                score=0.0,
            )
        try:
            import numpy as np
        except ImportError:
            raise ImportError("numpy is required for RelevancySimilarityMetric")

        similarity: np.ndarray = calculate_cosine_similarity(
            self._embeddings, contexts[0], prediction
        )
        return BaseEvaluationResult(
            prediction=prediction,
            contexts=contexts,
            score=float(similarity.mean()),
        )


class RetrieverMRRMetric(RetrieverEvaluationMetric):
    """Retriever Mean Reciprocal Rank metric.

    For each query, MRR evaluates the system’s accuracy by looking at the rank of the
    highest-placed relevant document. Specifically, it’s the average of the reciprocals
    of these ranks across all the queries. So, if the first relevant document is the
    top result, the reciprocal rank is 1; if it’s second, the reciprocal rank is 1/2,
    and so on.
    """

    def sync_compute(
        self,
        prediction: List[str],
        contexts: Optional[Sequence[str]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute MRR metric.

        Args:
            prediction(Optional[List[str]]): The retrieved chunks from the retriever.
            contexts(Optional[List[str]]): The contexts from dataset.
            query:(Optional[str]) The query text.
        Returns:
            BaseEvaluationResult: The evaluation result.
                The score is the reciprocal rank of the first relevant chunk.
        """
        if not prediction or not contexts:
            return BaseEvaluationResult(
                prediction=prediction,
                contexts=contexts,
                score=0.0,
            )
        for i, retrieved_chunk in enumerate(prediction):
            if retrieved_chunk in contexts:
                return BaseEvaluationResult(
                    score=1.0 / (i + 1),
                )
        return BaseEvaluationResult(
            score=0.0,
        )


class RetrieverHitRateMetric(RetrieverEvaluationMetric):
    """Retriever Hit Rate metric.

    Hit rate calculates the fraction of queries where the correct answer is found
    within the top-k retrieved documents. In simpler terms, it’s about how often our
    system gets it right within the top few guesses.
    """

    def sync_compute(
        self,
        prediction: List[str],
        contexts: Optional[Sequence[str]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute HitRate metric.

        Args:
            prediction(Optional[List[str]]): The retrieved chunks from the retriever.
            contexts(Optional[List[str]]): The contexts from dataset.
            query:(Optional[str]) The query text.
        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        if not prediction or not contexts:
            return BaseEvaluationResult(
                prediction=prediction,
                contexts=contexts,
                score=0.0,
            )
        is_hit = any(context in prediction for context in contexts)
        return BaseEvaluationResult(
            score=1.0 if is_hit else 0.0,
        )


class RetrieverEvaluator(Evaluator):
    """Evaluator for relevancy.

    Examples:
        .. code-block:: python

            import os
            import asyncio
            from dbgpt.rag.operators import (
                EmbeddingRetrieverOperator,
                RetrieverEvaluatorOperator,
            )
            from dbgpt.rag.evaluation import (
                RetrieverEvaluator,
                RetrieverSimilarityMetric,
            )
            from dbgpt.rag.embedding import DefaultEmbeddingFactory
            from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
            from dbgpt.storage.vector_store.connector import VectorStoreConnector
            from dbgpt.configs.model_config import MODEL_PATH, PILOT_PATH

            embeddings = DefaultEmbeddingFactory(
                default_model_name=os.path.join(MODEL_PATH, "text2vec-large-chinese"),
            ).create()
            vector_connector = VectorStoreConnector.from_default(
                "Chroma",
                vector_store_config=ChromaVectorConfig(
                    name="my_test_schema",
                    persist_path=os.path.join(PILOT_PATH, "data"),
                ),
                embedding_fn=embeddings,
            )

            dataset = [
                {
                    "query": "what is awel talk about",
                    "contexts": [
                        "Through the AWEL API, you can focus on the development"
                        " of business logic for LLMs applications without paying "
                        "attention to cumbersome model and environment details."
                    ],
                },
            ]
            evaluator = RetrieverEvaluator(
                operator_cls=EmbeddingRetrieverOperator,
                embeddings=embeddings,
                operator_kwargs={
                    "top_k": 5,
                    "vector_store_connector": vector_connector,
                },
            )
            results = asyncio.run(evaluator.evaluate(dataset))
    """

    def __init__(
        self,
        operator_cls: Type[RetrieverOperator],
        llm_client: Optional[LLMClient] = None,
        embeddings: Optional[Embeddings] = None,
        operator_kwargs: Optional[Dict] = None,
    ):
        """Create a new RetrieverEvaluator."""
        if not operator_kwargs:
            operator_kwargs = {}
        self._operator_cls = operator_cls
        self._operator_kwargs: Dict[str, Any] = operator_kwargs
        self.embeddings = embeddings
        super().__init__(llm_client=llm_client)

    async def evaluate(
        self,
        dataset: DatasetType,
        metrics: Optional[List[EvaluationMetric]] = None,
        query_key: str = "query",
        contexts_key: str = "contexts",
        prediction_key: str = "prediction",
        parallel_num: int = 1,
        **kwargs,
    ) -> List[List[EvaluationResult]]:
        """Evaluate the dataset."""
        from dbgpt.core.awel import DAG, IteratorTrigger, MapOperator

        if not metrics:
            if not self.embeddings:
                raise ValueError("embeddings are required for SimilarityMetric")
            metrics = [RetrieverSimilarityMetric(self.embeddings)]

        with DAG("relevancy_evaluation_dag"):
            input_task = IteratorTrigger(dataset)
            query_task: MapOperator = MapOperator(lambda x: x[query_key])
            retriever_task = self._operator_cls(**self._operator_kwargs)
            retriever_eva_task = RetrieverEvaluatorOperator(
                evaluation_metrics=metrics, llm_client=self.llm_client
            )
            input_task >> query_task
            query_task >> retriever_eva_task
            query_task >> retriever_task >> retriever_eva_task
            input_task >> MapOperator(lambda x: x[contexts_key]) >> retriever_eva_task
            input_task >> retriever_eva_task

        results = await input_task.trigger(parallel_num=parallel_num)
        return [item for _, item in results]
