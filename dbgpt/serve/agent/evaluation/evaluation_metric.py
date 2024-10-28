import json
import logging
from abc import ABC
from typing import Any, List, Optional

from dbgpt.core.interface.evaluation import (
    BaseEvaluationResult,
    EvaluationMetric,
    metric_manage,
)
from dbgpt.rag.evaluation.answer import AnswerRelevancyMetric
from dbgpt.rag.evaluation.retriever import (
    RetrieverHitRateMetric,
    RetrieverMRRMetric,
    RetrieverSimilarityMetric,
)

logger = logging.getLogger(__name__)


class AppLinkMetric(EvaluationMetric[str, str], ABC):
    """Intent evaluation  metric.
    Hit rate calculates the fraction of queries where the correct answer is found
    within the top-k retrieved documents. In simpler terms, it’s about how often our
    system gets it right within the top few guesses.
    """

    @classmethod
    @property
    def describe(cls) -> str:
        return "可以对AppLink的返回结果进行正确性判断计算！"

    def sync_compute(
        self,
        prediction: Optional[str] = None,
        contexts: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseEvaluationResult:
        """Compute Intent metric.
        Args:
            prediction(Optional[str]): The retrieved chunks from the retriever.
            contexts(Optional[str]): The contexts from dataset.
            query:(Optional[str]) The query text.
        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        score = 0
        prediction_result = None
        passing = True
        try:
            prediction_result = prediction
            if not prediction or len(prediction) <= 0:
                passing = False
            else:
                prediction_dict = json.loads(prediction)
                intent = prediction_dict.get("app_name", None)
                prediction_result = intent
                if intent in contexts:
                    score = 1
        except Exception as e:
            logger.warning(f"AppLinkMetric sync_compute exception {str(e)}")
            if prediction == contexts:
                score = 1

        return BaseEvaluationResult(
            score=score,
            prediction=prediction_result,
            passing=passing,
        )


class IntentMetric(EvaluationMetric[str, str], ABC):
    """Intent evaluation  metric.
    Hit rate calculates the fraction of queries where the correct answer is found
    within the top-k retrieved documents. In simpler terms, it’s about how often our
    system gets it right within the top few guesses.
    """

    @classmethod
    @property
    def describe(cls) -> str:
        return "可以对意图识别Agent的返回结果进行正确性判断计算！"

    def sync_compute(
        self,
        prediction: Optional[str] = None,
        contexts: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseEvaluationResult:
        """Compute Intent metric.
        Args:
            prediction(Optional[str]): The retrieved chunks from the retriever.
            contexts(Optional[str]): The contexts from dataset.
            query:(Optional[str]) The query text.
        Returns:
            BaseEvaluationResult: The evaluation result.
        """
        score = 0
        prediction_result = None
        try:
            prediction_result = prediction
            if not prediction:
                passing = False
            else:
                prediction_dict = json.loads(prediction)
                intent = prediction_dict.get("intent", None)
                prediction_result = intent
                if intent in contexts:
                    score = 1
                passing = True
        except Exception as e:
            print(f"warning {str(e)}")
            if prediction == contexts:
                score = 1

        return BaseEvaluationResult(
            score=score,
            prediction=prediction_result,
            passing=passing,
        )


metric_manage.register_metric(RetrieverHitRateMetric)
metric_manage.register_metric(RetrieverMRRMetric)
metric_manage.register_metric(RetrieverSimilarityMetric)
metric_manage.register_metric(AnswerRelevancyMetric)
