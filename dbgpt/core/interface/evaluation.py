"""Evaluation module."""
import asyncio
import string
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Generic,
    Iterator,
    List,
    Optional,
    Sequence,
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


class BaseEvaluationResult(BaseModel):
    """Base evaluation result."""

    prediction: Optional[PredictionType] = Field(
        None,
        description="Prediction data(including the output of LLM, the data from "
        "retrieval, etc.)",
    )
    contexts: Optional[ContextType] = Field(None, description="Context data")
    score: Optional[float] = Field(None, description="Score for the prediction")
    passing: Optional[bool] = Field(
        None, description="Binary evaluation result (passing or not)"
    )
    metric_name: Optional[str] = Field(None, description="Name of the metric")


class EvaluationResult(BaseEvaluationResult):
    """Evaluation result.

    Output of an BaseEvaluator.
    """

    query: Optional[QueryType] = Field(None, description="Query data")
    raw_dataset: Optional[Any] = Field(None, description="Raw dataset")


Q = TypeVar("Q")
P = TypeVar("P")
C = TypeVar("C")


class EvaluationMetric(ABC, Generic[P, C]):
    """Base class for evaluation metric."""

    @property
    def name(self) -> str:
        """Name of the metric."""
        return self.__class__.__name__

    async def compute(
        self,
        prediction: P,
        contexts: Optional[Sequence[C]] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric.

        Args:
            prediction(P): The prediction data.
            contexts(Optional[Sequence[C]]): The context data.

        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        return await asyncio.get_running_loop().run_in_executor(
            None, self.sync_compute, prediction, contexts
        )

    def sync_compute(
        self,
        prediction: P,
        contexts: Optional[Sequence[C]] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric.

        Args:
            prediction(P): The prediction data.
            contexts(Optional[Sequence[C]]): The context data.

        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        raise NotImplementedError("sync_compute is not implemented")


class FunctionMetric(EvaluationMetric[P, C], Generic[P, C]):
    """Evaluation metric based on a function."""

    def __init__(
        self,
        name: str,
        func: Callable[
            [P, Optional[Sequence[C]]],
            BaseEvaluationResult,
        ],
    ):
        """Create a FunctionMetric.

        Args:
            name(str): The name of the metric.
            func(Callable[[P, Optional[Sequence[C]]], BaseEvaluationResult]):
                The function to use for evaluation.
        """
        self._name = name
        self.func = func

    @property
    def name(self) -> str:
        """Name of the metric."""
        return self._name

    async def compute(
        self,
        prediction: P,
        context: Optional[Sequence[C]] = None,
    ) -> BaseEvaluationResult:
        """Compute the evaluation metric."""
        return self.func(prediction, context)


class ExactMatchMetric(EvaluationMetric[str, str]):
    """Exact match metric.

    Just support string prediction and context.
    """

    def __init__(self, ignore_case: bool = False, ignore_punctuation: bool = False):
        """Create an ExactMatchMetric."""
        self._ignore_case = ignore_case
        self._ignore_punctuation = ignore_punctuation

    async def compute(
        self,
        prediction: str,
        contexts: Optional[Sequence[str]] = None,
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

    def __init__(self, embeddings: Embeddings):
        """Create a SimilarityMetric with embeddings."""
        self._embeddings = embeddings

    def sync_compute(
        self,
        prediction: str,
        contexts: Optional[Sequence[str]] = None,
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
        **kwargs
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
