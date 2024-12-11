import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from dbgpt.core import Embeddings, LLMClient
from dbgpt.core.awel import IteratorTrigger, JoinOperator, MapOperator
from dbgpt.core.awel.task.base import IN, OUT
from dbgpt.core.interface.evaluation import (
    EVALUATE_FILE_COL_ANSWER,
    EVALUATE_FILE_COL_PREDICTION,
    EVALUATE_FILE_COL_PREDICTION_COST,
    EVALUATE_FILE_COL_QUESTION,
    DatasetType,
    EvaluationMetric,
    EvaluationResult,
    Evaluator,
)
from dbgpt.rag.evaluation import RetrieverSimilarityMetric
from dbgpt.serve.agent.agents.controller import multi_agents

logger = logging.getLogger(__name__)


class AgentOutputOperator(MapOperator):
    def __init__(self, app_code: str, **kwargs):
        """
        Args:
            space_name (str): The space name.
            recall_score (Optional[float], optional): The recall score. Defaults to 0.3.
        """
        self.app_code = app_code
        super().__init__(**kwargs)

    async def map(self, input_value: IN) -> OUT:
        logger.info(f"AgentOutputOperator map:{input_value}")

        final_output = None
        try:
            begin_time_ms = int(datetime.now().timestamp())
            async for output in multi_agents.app_agent_chat(
                conv_uid=str(uuid.uuid1()),
                gpts_name=self.app_code,
                user_query=input_value,
                user_code="",
                sys_code="",
                enable_verbose=False,
                stream=False,
            ):
                role = "assistant"
                content = output
                if isinstance(output, dict):
                    content = output["markdown"]
                    role = output["sender"]
                    model = output["model"]
                    if model is None:
                        continue

                    final_output = content
            end_time_ms = int(datetime.now().timestamp())
            cost_time_ms = begin_time_ms - end_time_ms
            result = {}
            result[EVALUATE_FILE_COL_PREDICTION] = final_output
            result[EVALUATE_FILE_COL_PREDICTION_COST] = cost_time_ms
            return result
        except Exception as e:
            logger.warning(f"{input_value} agent evalute faild!{str(e)}")
            return None


class AgentEvaluatorOperator(JoinOperator[List[EvaluationResult]]):
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
        prediction_result: dict,
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
        prediction = prediction_result.get(EVALUATE_FILE_COL_PREDICTION, None)
        prediction_cost = prediction_result.get(EVALUATE_FILE_COL_PREDICTION_COST, None)
        for metric in self.evaluation_metrics:
            tasks.append(metric.compute(prediction, contexts))
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
                    prediction_cost=prediction_cost,
                    feedback=result.feedback,
                )
            )
        return results


class AgentEvaluator(Evaluator):
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
        operator_cls: Type[MapOperator],
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
        query_key: str = EVALUATE_FILE_COL_QUESTION,
        contexts_key: str = EVALUATE_FILE_COL_ANSWER,
        prediction_key: str = EVALUATE_FILE_COL_PREDICTION,
        parallel_num: int = 1,
        **kwargs,
    ) -> List[List[EvaluationResult]]:
        """Evaluate the dataset."""
        from dbgpt.core.awel import DAG, MapOperator

        if not metrics:
            if not self.embeddings:
                raise ValueError("embeddings are required for SimilarityMetric")
            metrics = [RetrieverSimilarityMetric(self.embeddings)]

        def _query_task_func(x):
            logger.info(x)
            return x[query_key]

        with DAG("agent_evaluation_dag"):
            input_task = IteratorTrigger(dataset)
            query_task: MapOperator = MapOperator(_query_task_func)
            agent_output_task = self._operator_cls(**self._operator_kwargs)
            agent_eva_task = AgentEvaluatorOperator(
                evaluation_metrics=metrics, llm_client=self.llm_client
            )
            input_task >> query_task
            query_task >> agent_eva_task
            query_task >> agent_output_task >> agent_eva_task
            input_task >> MapOperator(lambda x: x[contexts_key]) >> agent_eva_task
            input_task >> agent_eva_task

        if parallel_num > len(dataset):
            parallel_num = len(dataset)

        results = await input_task.trigger(parallel_num=parallel_num)
        return [item for _, item in results]
