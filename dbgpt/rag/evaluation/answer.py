"""Evaluation answer."""
import asyncio
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from dbgpt.core import HumanPromptTemplate, ModelMessage
from dbgpt.core.awel import IteratorTrigger, JoinOperator, MapOperator
from dbgpt.core.interface.evaluation import (
    DatasetType,
    EvaluationMetric,
    EvaluationResult,
    Evaluator,
)
from dbgpt.core.interface.llm import LLMClient, ModelRequest

logger = logging.getLogger(__name__)

ANSWER_RELEVANCY_EVALUATE_PROMPT_TEMPLATE = """
你是一个智能答疑专家, 你的任务是根据用户的问题和已经相关的文档给问答的答案进行严格的打分.

你将会得到以下输入信息:
- 用户的问题
- 答案的知识来源，用于评估中的参考.
- 问答系统生成的答案

约束条件:
- 你的工作是判断生成回答的相关性和正确性，并且输出一个代表整体评价的单一得分。
- 你所返回的答案必须包含一个得分，且只能包含得分。
- 不能返回任何其他格式的答案。
在另外一行中需要提供你对得分的理由。

遵循以下评分指南：
你的得分必须在0到5之间，其中0是最差的，5是最好的。
如果生成的答案包含LLM ERROR信息，你应该给出0分。
如果生成的答案与相关的参考内容基本不相关，你应该给出1分。
如果生成的答案与相关的参考内容有点相关，但回答并没有十分的详细，你应该给出2分。
如果生成的答案与相关的参考内容非常相关，但回答并没有十分的详细，你应该给出3分。
如果生成的答案与相关的参考内容相关且完全正确，并且十分详细地回答用户的问题，你应该给出4分。
如果生成的答案与相关的参考内容相关且完全正确，并且十分详细地回答用户的问题，还有自己的建议和思考，你应该给出5分。

用户的问题是:
{query}
相关的参考:
{context}
模型生成的答案:
{answer}

Example Response:
4.0
如果生成的答案与相关的参考内容相关且完全正确，并且十分详细地回答用户的问题，你应该给出4分。

"""


class LLMEvaluationMetric(EvaluationMetric):
    """LLM Relevancy metric."""

    prompt_template = ANSWER_RELEVANCY_EVALUATE_PROMPT_TEMPLATE

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: Optional[str] = None,
        prompt_template: Optional[str] = None,
    ):
        """Create a SimilarityMetric with embeddings."""
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = prompt_template

    async def compute(
        self,
        prediction: str,
        contexts: Optional[Sequence[str]] = None,
        query: Optional[str] = None,
    ) -> EvaluationResult:
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
            return EvaluationResult(
                query=query,
                prediction=prediction,
                contexts=contexts,
                score=0.0,
            )
        evaluate_result = await self._generate_llm_result(query, prediction, contexts)
        score, feedback = self._parse_evaluate_response(evaluate_result)
        return EvaluationResult(
            query=query,
            prediction=prediction,
            contexts=contexts,
            score=score,
            feedback=feedback,
        )

    async def _generate_llm_result(
        self,
        query: str | None = None,
        answer: str | None = None,
        contexts: Optional[Sequence[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Generate llm result."""
        template = HumanPromptTemplate.from_template(self._prompt_template)
        messages = template.format_messages(
            query=query, context=contexts, answer=answer
        )
        if not self._model_name:
            models = await self._llm_client.models()
            if not models:
                raise Exception("No models available")
            self._model_name = models[0].model
            logger.info(f"Using model {self._model_name} to evaluate")

        model_messages = ModelMessage.from_base_messages(messages)
        request = ModelRequest(model=self._model_name, messages=model_messages)
        response = await self._llm_client.generate(request=request)

        if not response.success:
            code = str(response.error_code)
            reason = response.text
            logger.error(f"request llm failed ({code}) {reason}")
            return f"request llm failed ({code}) {reason}"
        return response.text

    @abstractmethod
    def _parse_evaluate_response(
        self, response: str, limit: Optional[int] = None
    ) -> Tuple[Any, Any]:
        """Parse llm evaluate response."""


class AnswerRelevancyMetric(LLMEvaluationMetric):
    """Answer Relevancy metric."""

    prompt_template = ANSWER_RELEVANCY_EVALUATE_PROMPT_TEMPLATE

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: Optional[str] = None,
        prompt_template: Optional[str] = None,
    ):
        """Create a AnswerRelevancyMetric with llm_client.

        Args:
            llm_client(LLMClient): The llm client to use for evaluation.
            model_name(str): The model name to use for evaluation.
            prompt_template(Optional[str]): The prompt template to use for evaluation.
        """
        self._llm_client = llm_client
        self._model_name = model_name
        self._prompt_template = (
            prompt_template or ANSWER_RELEVANCY_EVALUATE_PROMPT_TEMPLATE
        )
        super().__init__(self._llm_client, self._model_name, self._prompt_template)

    def _parse_evaluate_response(
        self, text: str, limit: Optional[int] = None
    ) -> Tuple[Any, Any]:
        parts = text.split("\\n", 1)
        score = parts[0].strip()
        try:
            score = float(score)  # type: ignore # noqa
        except ValueError as e:
            logger.error(f"Error converting \\n score to float: {e}")
            parts = text.split("\n", 1)
            score = parts[0].strip()
            try:
                score = float(score)  # type: ignore # noqa
            except ValueError as e:
                logger.error(f"Error converting score to float: {e}")
                return 0.0, "parse score float error."
        feedback = parts[1].strip() if len(parts) > 1 else None
        return score, feedback


class LLMAnswerEvaluator(Evaluator):
    """Evaluator for LLM Answer relevancy."""

    def __init__(
        self,
        operator_cls: Type[MapOperator],
        llm_client: Optional[LLMClient] = None,
        operator_kwargs: Optional[Dict] = None,
    ):
        """Create a new LLMAnswerEvaluator."""
        if not operator_kwargs:
            operator_kwargs = {}
        self._operator_cls = operator_cls
        self._operator_kwargs: Dict[str, Any] = operator_kwargs
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
        from dbgpt.core.awel import DAG, MapOperator

        if not metrics:
            if not self.llm_client:
                raise ValueError("llm_client are required for AnswerRelevancyMetric")
            metrics = [AnswerRelevancyMetric(self.llm_client)]

        with DAG("relevancy_evaluation_dag"):
            input_task = IteratorTrigger(dataset)
            query_task: MapOperator = MapOperator(lambda x: x[query_key])
            answer_output_task = self._operator_cls(**self._operator_kwargs)
            answer_eva_task = AnswerEvaluatorOperator(
                evaluation_metrics=metrics, llm_client=self.llm_client  # type: ignore # noqa
            )
            input_task >> query_task
            query_task >> answer_eva_task
            query_task >> answer_output_task >> answer_eva_task
            input_task >> MapOperator(lambda x: x[contexts_key]) >> answer_eva_task
            input_task >> answer_eva_task

        results = await input_task.trigger(parallel_num=parallel_num)
        return [item for _, item in results]


class AnswerEvaluatorOperator(JoinOperator[List[EvaluationResult]]):
    """Evaluator for Answer."""

    def __init__(
        self,
        evaluation_metrics: List[LLMEvaluationMetric],
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        """Create a new AnswerEvaluatorOperator.

        Args:
            evaluation_metrics(List[LLMEvaluationMetric]): The evaluation metrics.
            llm_client(Optional[LLMClient]): The llm client to use for evaluation.
        """
        self.llm_client = llm_client
        self.evaluation_metrics = evaluation_metrics
        super().__init__(combine_function=self._do_evaluation, **kwargs)

    async def _do_evaluation(
        self,
        query: str,
        prediction: List[str],
        contexts: List[str],
        raw_dataset: Any = None,
    ) -> List[EvaluationResult]:
        """Run evaluation.

        Args:
            query(str): The query string.
            prediction(List[str]): The retrieved chunks from the retriever.
            contexts(List[str]): The contexts from dataset.
            raw_dataset(Any): The raw data(single row) from dataset.
        """
        if isinstance(contexts, str):
            contexts = [contexts]
        tasks = []
        for metric in self.evaluation_metrics:
            tasks.append(metric.compute(query, prediction, contexts))  # type: ignore # noqa
        task_results = await asyncio.gather(*tasks)
        results = []
        for result, metric in zip(task_results, self.evaluation_metrics):
            results.append(
                EvaluationResult(
                    query=query,
                    prediction=result.prediction,
                    score=result.score,
                    contexts=contexts,
                    passing=result.passing,
                    raw_dataset=raw_dataset,
                    metric_name=metric.name(),
                    feedback=result.feedback,
                )
            )
        return results
