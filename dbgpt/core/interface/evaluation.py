"""Evaluation module."""
import asyncio
import string
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Generic,
    Iterator,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.util.similarity_util import calculate_cosine_similarity

from .embeddings import Embeddings
from .llm import LLMClient

if TYPE_CHECKING:
    from dbgpt.core.awel.task.base import InputSource

QueryType = Union[str, Any]
PredictionType = Union[str, Any]
ContextType = Union[str, Sequence[str], Any]
DatasetType = Union["InputSource", Iterator, AsyncIterator]

EVALUATE_FILE_COL_QUESTION = "query"
EVALUATE_FILE_COL_ANSWER = "factual"
EVALUATE_FILE_COL_PREDICTION = "prediction"
EVALUATE_FILE_COL_PREDICTION_COST = "prediction_cost"


class BaseEvaluationResult(BaseModel):
    """Base evaluation result."""

    prediction: Optional[PredictionType] = Field(
        None,
        description="Prediction data(including the output of LLM, the data from "
        "retrieval, etc.)",
    )
    contexts: Optional[ContextType] = Field(None, description="Context data")
    score: Optional[float] = Field(
        None, description="Score for the prediction in now metric"
    )
    passing: Optional[bool] = Field(
        True, description="Determine whether the current prediction result is valid"
    )
    metric_name: Optional[str] = Field(None, description="Name of the metric")
    prediction_cost: int = 0


class EvaluationResult(BaseEvaluationResult):
    """Evaluation result.

    Output of an BaseEvaluator.
    """

    query: Optional[QueryType] = Field(None, description="Query data")
    raw_dataset: Optional[Any] = Field(None, description="Raw dataset")
    feedback: Optional[str] = Field(None, description="feedback")


Q = TypeVar("Q")
P = TypeVar("P")
C = TypeVar("C")


class EvaluationMetric(ABC, Generic[P, C]):
    """Base class for evaluation metric."""

    def __init__(self, **kwargs):  # noqa
        pass

    @classmethod
    def name(cls) -> str:
        """Name of the metric."""
        return cls.__name__

    @classmethod
    def describe(cls) -> str:
        """Describe."""
        return f"This is an evaluation result index calculation tool, named {cls.name} "

    async def compute(
        self,
        prediction: P,
        contexts: Optional[Sequence[C]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric.

        Args:
            prediction(P): The prediction data.
            contexts(Optional[Sequence[C]]): The context data.
            query:(Optional[str]) The query text.

        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        return await asyncio.get_running_loop().run_in_executor(
            None, self.sync_compute, prediction, contexts, query
        )

    def sync_compute(
        self,
        prediction: P,
        contexts: Optional[Sequence[C]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric.

        Args:
            prediction(P): The prediction data.
            contexts(Optional[Sequence[C]]): The factual data.
            query:(Optional[str]) The query text.

        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        raise NotImplementedError("sync_compute is not implemented")


class FunctionMetric(EvaluationMetric[P, C], Generic[P, C]):
    """Evaluation metric based on a function."""

    def __init__(self, **kwargs):
        """Create a FunctionMetric.

        Args:
            name(str): The name of the metric.
            func(Callable[[P, Optional[Sequence[C]]], BaseEvaluationResult]):
                The function to use for evaluation.
        """
        if "name" not in kwargs:
            raise ValueError("Must need param name")

        if "func" not in kwargs:
            raise ValueError("Must need param func")
        self._name = kwargs.get("name", None)
        self.func = kwargs.get("func", None)

    @property
    def name(self) -> str:  # type: ignore # noqa
        """Name of the metric."""
        return self._name

    async def compute(
        self,
        prediction: P,
        context: Optional[Sequence[C]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric."""
        return self.func(prediction, context)


class ExactMatchMetric(EvaluationMetric[str, str]):
    """Exact match metric.

    Just support string prediction and context.
    """

    def __init__(self, **kwargs):
        """Create an ExactMatchMetric."""
        self._ignore_case = kwargs.get("ignore_case", False)
        self._ignore_punctuation = kwargs.get("ignore_punctuation", False)

    async def compute(
        self,
        prediction: str,
        contexts: Optional[Sequence[str]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric."""
        if self._ignore_case:
            prediction = prediction.lower()
            if contexts:
                contexts = [c.lower() for c in contexts]
        if self._ignore_punctuation:
            prediction = prediction.translate(str.maketrans("", "", string.punctuation))
            if contexts:
                contexts = [
                    c.translate(str.maketrans("", "", string.punctuation))
                    for c in contexts
                ]
        score = 0 if not contexts else float(prediction in contexts)
        return BaseEvaluationResult(
            prediction=prediction,
            contexts=contexts,
            score=score,
        )


class SimilarityMetric(EvaluationMetric[str, str]):
    """Similarity metric.

    Calculate the cosine similarity between a prediction and a list of contexts.
    """

    def __init__(self, **kwargs):
        """Create a SimilarityMetric with embeddings."""
        self._embeddings = kwargs.get("embeddings", None)
        if self._embeddings is None or not isinstance(self._embeddings, Embeddings):
            raise ValueError("Need embedding service！")

    def sync_compute(
        self,
        prediction: str,
        contexts: Optional[Sequence[str]] = None,
        query: Optional[str] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric."""
        if not contexts:
            return BaseEvaluationResult(
                prediction=prediction,
                contexts=contexts,
                score=0.0,
            )
        try:
            import numpy as np
        except ImportError:
            raise ImportError("numpy is required for SimilarityMetric")

        similarity: np.ndarray = calculate_cosine_similarity(
            self._embeddings, prediction, contexts
        )
        return BaseEvaluationResult(
            prediction=prediction,
            contexts=contexts,
            score=float(similarity.mean()),
        )


class Evaluator(ABC):
    """Base Evaluator class."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
    ):
        """Create an Evaluator."""
        self.llm_client = llm_client

    @abstractmethod
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
        """Run evaluation with a dataset and metrics.

        Args:
            dataset(DatasetType): The dataset to evaluate.
            metrics(Optional[List[EvaluationMetric]]): The metrics to use for
                evaluation.
            query_key(str): The key for query in the dataset.
            contexts_key(str): The key for contexts in the dataset.
            prediction_key(str): The key for prediction in the dataset.
            parallel_num(int): The number of parallel tasks.
            kwargs: Additional arguments.

        Returns:
            List[List[EvaluationResult]]: The evaluation results, the length of the
                result equals to the length of the dataset. The first element in the
                list is the list of evaluation results for metrics.
        """


class MetricManage:
    """MetricManage."""

    def __init__(self):
        """Init metricManage."""
        self.metrics = defaultdict()

    def register_metric(self, cls: Type[EvaluationMetric]):
        """Register metric."""
        self.metrics[cls.name()] = cls

    def get_by_name(self, name: str) -> Type[EvaluationMetric]:
        """Get by name."""
        if name not in self.metrics:
            raise ValueError(f"Metric:{name} not register!")
        return self.metrics[name]

    def all_metric_infos(self):
        """Get all metric infos."""
        result = []
        for name, cls in self.metrics.items():
            result.append(
                {
                    "name": name,
                    "describe": cls.describe,
                }
            )
        return result


metric_manage = MetricManage()
