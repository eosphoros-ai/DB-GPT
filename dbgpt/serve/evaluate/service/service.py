import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from dbgpt._private.config import Config
from dbgpt.component import ComponentType, SystemApp
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.core.interface.evaluation import (
    EVALUATE_FILE_COL_ANSWER,
    EvaluationResult,
    metric_manage,
)
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.evaluation import RetrieverEvaluator
from dbgpt.rag.evaluation.answer import AnswerRelevancyMetric
from dbgpt.rag.evaluation.retriever import RetrieverSimilarityMetric
from dbgpt.serve.rag.operators.knowledge_space import SpaceRetrieverOperator
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.vector_store.base import VectorStoreConfig

from ...agent.agents.controller import multi_agents
from ...agent.evaluation.evaluation import AgentEvaluator, AgentOutputOperator
from ...agent.evaluation.evaluation_metric import IntentMetric
from ...core import BaseService
from ...prompt.service.service import Service as PromptService
from ...rag.connector import VectorStoreConnector
from ...rag.service.service import Service as RagService
from ..api.schemas import EvaluateServeRequest, EvaluateServeResponse, EvaluationScene
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity

logger = logging.getLogger(__name__)

CFG = Config()
executor = ThreadPoolExecutor(max_workers=5)


def get_rag_service(system_app) -> RagService:
    return system_app.get_component("dbgpt_rag_service", RagService)


def get_prompt_service(system_app) -> PromptService:
    return system_app.get_component("dbgpt_serve_prompt_service", PromptService)


class Service(BaseService[ServeEntity, EvaluateServeRequest, EvaluateServeResponse]):
    """The service class for Evaluate"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, dao: Optional[ServeDao] = None):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: ServeDao = dao
        super().__init__(system_app)
        self.rag_service = get_rag_service(system_app)
        self.prompt_service = get_prompt_service(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._system_app = system_app

    @property
    def dao(self) -> BaseDao[ServeEntity, EvaluateServeRequest, EvaluateServeResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    async def run_evaluation(
        self,
        scene_key,
        scene_value,
        datasets: List[dict],
        context: Optional[dict] = None,
        evaluate_metrics: Optional[List[str]] = None,
        parallel_num: Optional[int] = 1,
    ) -> List[List[EvaluationResult]]:
        """Evaluate results

        Args:
            scene_key (str): The scene_key
            scene_value (str): The scene_value
            datasets (List[dict]): The datasets
            context (Optional[dict]): The run context
            evaluate_metrics (Optional[str]): The metric_names
            parallel_num (Optional[int]): The parallel_num

        Returns:
            List[List[EvaluationResult]]: The response
        """

        results = []
        if EvaluationScene.RECALL.value == scene_key:
            embedding_factory = CFG.SYSTEM_APP.get_component(
                "embedding_factory", EmbeddingFactory
            )
            embeddings = embedding_factory.create(
                EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
            )

            config = VectorStoreConfig(
                name=scene_value,
                embedding_fn=embeddings,
            )
            vector_store_connector = VectorStoreConnector(
                vector_store_type=CFG.VECTOR_STORE_TYPE,
                vector_store_config=config,
            )
            evaluator = RetrieverEvaluator(
                operator_cls=SpaceRetrieverOperator,
                embeddings=embeddings,
                operator_kwargs={
                    "space_id": str(scene_value),
                    "top_k": CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                    "vector_store_connector": vector_store_connector,
                },
            )
            metrics = []
            metric_name_list = evaluate_metrics
            for name in metric_name_list:
                if name == "RetrieverSimilarityMetric":
                    metrics.append(RetrieverSimilarityMetric(embeddings=embeddings))
                else:
                    metrics.append(metric_manage.get_by_name(name)())

            for dataset in datasets:
                chunks = self.rag_service.get_chunk_list(
                    {"doc_name": dataset.get("doc_name")}
                )
                contexts = [chunk.content for chunk in chunks]
                dataset["contexts"] = contexts
            results = await evaluator.evaluate(
                datasets, metrics=metrics, parallel_num=parallel_num
            )
        elif EvaluationScene.APP.value == scene_key:
            evaluator = AgentEvaluator(
                operator_cls=AgentOutputOperator,
                operator_kwargs={
                    "app_code": scene_value,
                },
            )

            metrics = []
            metric_name_list = evaluate_metrics
            for name in metric_name_list:
                if name == AnswerRelevancyMetric.name():
                    worker_manager = CFG.SYSTEM_APP.get_component(
                        ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
                    ).create()
                    llm_client = DefaultLLMClient(worker_manager=worker_manager)
                    prompt = self.prompt_service.get_template(context.get("prompt"))
                    metrics.append(
                        AnswerRelevancyMetric(
                            llm_client=llm_client,
                            model_name=context.get("model"),
                            prompt_template=prompt.template,
                        )
                    )
                    for dataset in datasets:
                        context = await multi_agents.get_knowledge_resources(
                            app_code=scene_value, question=dataset.get("query")
                        )
                        dataset[EVALUATE_FILE_COL_ANSWER] = context
                else:
                    metrics.append(metric_manage.get_by_name(name)())
            results = await evaluator.evaluate(
                dataset=datasets, metrics=metrics, parallel_num=parallel_num
            )
        return results
