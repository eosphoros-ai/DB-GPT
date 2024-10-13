import asyncio
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import chardet
import pandas as pd

from dbgpt._private.config import Config
from dbgpt.agent.core.schema import Status
from dbgpt.component import ComponentType, SystemApp
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.core.interface.evaluation import (
    EVALUATE_FILE_COL_ANSWER,
    EVALUATE_FILE_COL_PREDICTION,
    EVALUATE_FILE_COL_PREDICTION_COST,
    EvaluationResult,
    metric_manage,
)
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.evaluation import RetrieverEvaluator
from dbgpt.rag.evaluation.answer import AnswerRelevancyMetric
from dbgpt.rag.evaluation.retriever import RetrieverSimilarityMetric
from dbgpt.serve.core import BaseService, Result
from dbgpt.serve.rag.operators.knowledge_space import SpaceRetrieverOperator
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.util.oss_utils import a_get_object, a_put_object
from dbgpt.util.pagination_utils import PaginationResult

from ...agent.agents.controller import multi_agents
from ...agent.evaluation.evaluation import AgentEvaluator, AgentOutputOperator
from ...agent.evaluation.evaluation_metric import IntentMetric
from ...prompt.service.service import Service as PromptService
from ...rag.connector import VectorStoreConnector
from ...rag.service.service import Service as RagService
from ..api.schemas import (
    DatasetServeRequest,
    DatasetServeResponse,
    DatasetStorageType,
    EvaluateServeRequest,
    EvaluateServeResponse,
    EvaluationScene,
)
from ..config import (
    SERVE_CONFIG_KEY_PREFIX,
    SERVE_DATASET_SERVICE_COMPONENT_NAME,
    SERVE_SERVICE_COMPONENT_NAME,
    ServeConfig,
)
from ..models.models import ServeDao, ServeEntity
from .service_dataset import DatasetService

logger = logging.getLogger(__name__)

CFG = Config()
executor = ThreadPoolExecutor(max_workers=5)


def get_dataset_service(system_app) -> DatasetService:
    return system_app.get_component(
        SERVE_DATASET_SERVICE_COMPONENT_NAME, DatasetService
    )


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
        self.dataset_service = get_dataset_service(system_app)
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
        self._dao = self._dao or ServeDao(self._serve_config)
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
                if name == AnswerRelevancyMetric.name:
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

    async def _evaluation_executor(self, request, dataset_info, evaluation_record):
        (
            datasets_info,
            datasets_content,
        ) = await self.dataset_service.get_dataset_json_record(dataset_info)
        err_msg = None
        results = None
        try:
            self.dao.update(
                {"evaluate_code": evaluation_record.evaluate_code},
                EvaluateServeRequest(
                    state=Status.RUNNING.value, storage_type=datasets_info.storage_type
                ),
            )
            results: List[List[EvaluationResult]] = await self.run_evaluation(
                request.scene_key,
                request.scene_value,
                datasets_content,
                request.context,
                request.evaluate_metrics,
                request.parallel_num,
            )
        except Exception as e:
            logger.exception("run_evaluation exception!")
            status = Status.FAILED.value
            err_msg = "evaluate error:" + str(e)
        update_request = EvaluateServeRequest()
        try:
            if results:
                datasets_map = {d["query"]: d for d in datasets_content}

                total_prediction_cost = 0
                metric_score_map = {}
                metric_valid_count_map = {}
                temps = []
                for result in results:
                    query = result[0].query
                    dataset_item = datasets_map.get(query)
                    if dataset_item:
                        dataset_item.update(
                            {EVALUATE_FILE_COL_PREDICTION: result[0].prediction}
                        )
                        dataset_item.update(
                            {
                                EVALUATE_FILE_COL_PREDICTION_COST: result[
                                    0
                                ].prediction_cost
                            }
                        )
                        if result[0].feedback:
                            dataset_item.update({"feedback": result[0].feedback})
                        for item in result:
                            # 指标有效计数
                            vaild_count = 1
                            if item.passing:
                                if item.metric_name in metric_valid_count_map:
                                    vaild_count = (
                                        metric_valid_count_map[item.metric_name] + 1
                                    )

                            metric_valid_count_map[item.metric_name] = vaild_count

                            # metric total score
                            total_score = item.score
                            if item.metric_name in metric_score_map:
                                total_score = (
                                    metric_score_map[item.metric_name] + item.score
                                )
                            metric_score_map[item.metric_name] = total_score

                            dataset_item.update({item.metric_name: item.score})
                            temps.append(item.dict())
                metric_average_score_map = {}

                for k, v in metric_score_map.items():
                    logger.info(f"evaluate total nums:{k}:{ metric_valid_count_map[k]}")
                    average_score = v / metric_valid_count_map[k]
                    metric_average_score_map[k] = average_score

                print(json.dumps(temps))

                # evaluate result
                if DatasetStorageType.OSS.value == datasets_info.storage_type:
                    result_df = pd.DataFrame(datasets_map.values())
                    if datasets_info.file_type.endswith(
                        ".xlsx"
                    ) or datasets_info.file_type.endswith(".xls"):
                        file_stream = io.BytesIO()
                        with pd.ExcelWriter(file_stream, engine="xlsxwriter") as writer:
                            result_df.to_excel(writer, index=False)

                        file_stream.seek(0)
                        file_string = file_stream.getvalue()
                    elif datasets_info.file_type.endswith(".csv"):
                        file_string = result_df.to_csv(
                            index=False, encoding="utf-8-sig"
                        )

                    else:
                        logger.warn(f"not support file type{datasets_info.file_type}")
                    result_oss_key = f"{evaluation_record.evaluate_code}_{datasets_info.name}(结果){datasets_info.file_type}"
                    await a_put_object(oss_key=result_oss_key, data=file_string)
                    update_request.result = result_oss_key
                else:
                    update_request.result = json.dumps(datasets_map.values())

                update_request.average_score = json.dumps(metric_average_score_map)
                status = Status.COMPLETE.value
        except Exception as e:
            logger.exception("evaluate service error.")
            status = Status.FAILED.value
            err_msg = "evaluate service error: " + str(e)
        update_request.state = status
        update_request.log_info = err_msg
        self.dao.update(
            {"evaluate_code": evaluation_record.evaluate_code}, update_request
        )

    def _check_permissions(self, response, user_id, user_name):
        if response and response.user_id == user_id:
            return True
        raise ValueError(f"你没有当前评测记录{response.evaluate_code}的权限!")

    async def get_evaluation_file_stream(self, evaluate_code: str):
        logger.info(f"get_evaluation_file_stream:{evaluate_code}")

        evaluation = self.get(EvaluateServeRequest(evaluate_code=evaluate_code))
        if evaluation:
            if Status.COMPLETE.value == evaluation.state:

                if evaluation.storage_type == "oss":
                    dataset_bytes = await a_get_object(oss_key=evaluation.result)
                    return evaluation.result, io.BytesIO(dataset_bytes)
                else:
                    datasets_dicts = json.loads(evaluation.result)
                    datasets_df = pd.DataFrame(datasets_dicts)

                    file_string = datasets_df.to_csv(index=False, encoding="utf-8-sig")

                    return f"{evaluation.evaluate_code}.csv", io.BytesIO(file_string)
            else:
                raise ValueError("evaluation have not complete yet.")
        else:
            raise ValueError(f"unknown evaluation record[{evaluate_code}]")

    async def get_evaluation_dicts(self, evaluate_code: str):
        logger.info(f"get_evaluation_file_stream:{evaluate_code}")

        evaluation = self.get(EvaluateServeRequest(evaluate_code=evaluate_code))
        if evaluation:
            if Status.COMPLETE.value == evaluation.state:
                if evaluation.storage_type == "oss":
                    file_content = await a_get_object(oss_key=evaluation.result)
                    result = chardet.detect(file_content)
                    encoding = result["encoding"]
                    if evaluation.result.endswith(
                        ".xlsx"
                    ) or evaluation.result.endswith(".xls"):
                        df_tmp = pd.read_excel(
                            io.BytesIO(file_content), index_col=False
                        )
                    elif evaluation.result.endswith(".csv"):
                        df_tmp = pd.read_csv(
                            io.BytesIO(file_content),
                            index_col=False,
                            encoding=encoding,
                        )
                    else:
                        raise ValueError(
                            f"evaluate do not support {evaluation.result}."
                        )

                    return df_tmp.to_dict(orient="records")
                else:
                    datasets_dicts = json.loads(evaluation.result)
                    return datasets_dicts
            else:
                raise ValueError("evaluation have not complete yet.")
        else:
            raise ValueError(f"unknown evaluation record[{evaluate_code}]")

    def run_slow_task(self, async_func, *args):
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError as e:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(async_func(*args), loop)
            else:
                loop.run_until_complete(async_func(*args))

        except Exception as e:
            logger.error("evaluation run error", e)

    async def new_evaluation(self, request: EvaluateServeRequest) -> Result:
        logger.info(f"new_evaluation:{request}")

        """New evaluation

        Args:
            request (EvaluateServeRequest): The request

        Returns:
            EvaluateServeResponse: The response
        """

        dataset_info: DatasetServeResponse = self.dataset_service.get(
            DatasetServeRequest(code=request.datasets)
        )
        request.datasets_name = dataset_info.name

        request.state = Status.TODO.value
        new_evaluation = self.create(request)

        executor.submit(
            self.run_slow_task,
            self._evaluation_executor,
            request,
            dataset_info,
            new_evaluation,
        )

        # asyncio.create_task(self.run_slow_bound_task(request, dataset_info, new_evaluation))
        return new_evaluation

    def create(self, request: EvaluateServeRequest) -> EvaluateServeResponse:
        """Create a new Evaluate entity

        Args:
            request (EvaluateServeRequest): The request

        Returns:
            EvaluateServeResponse: The response
        """

        if not request.user_name:
            request.user_name = self.config.default_user
        if not request.sys_code:
            request.sys_code = self.config.default_sys_code
        return super().create(request)

    def update(self, request: EvaluateServeRequest) -> EvaluateServeResponse:
        """Update a Evaluate entity

        Args:
            request (EvaluateServeRequest): The request

        Returns:
            EvaluateServeResponse: The response
        """
        # Build the query request from the request
        query_request = {
            "prompt_code": request.prompt_code,
            "sys_code": request.sys_code,
        }
        return self.dao.update(query_request, update_request=request)

    def get(self, request: EvaluateServeRequest) -> Optional[EvaluateServeResponse]:
        """Get a Evaluate entity

        Args:
            request (EvaluateServeRequest): The request

        Returns:
            EvaluateServeResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_one(query_request)

    def delete(self, request: EvaluateServeRequest) -> None:
        """Delete a Evaluate entity

        Args:
            request (EvaluateServeRequest): The request
        """
        # Build the query request from the request
        query_request = {
            "evaluate_code": request.evaluate_code,
            "user_id": request.user_id,
        }
        self.dao.delete(query_request)

    def get_list(self, request: EvaluateServeRequest) -> List[EvaluateServeResponse]:
        """Get a list of Evaluate entities

        Args:
            request (EvaluateServeRequest): The request

        Returns:
            List[EvaluateServeResponse]: The response
        """
        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: EvaluateServeRequest, page: int, page_size: int
    ) -> PaginationResult[EvaluateServeResponse]:
        """Get a list of Evaluate entities by page

        Args:
            request (EvaluateServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[EvaluateServeResponse]: The response
        """
        query_request = request
        return self.dao.get_list_page(
            query_request, page, page_size, ServeEntity.id.name
        )
