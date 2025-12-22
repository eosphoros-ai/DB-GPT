import io
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from dbgpt.agent.core.schema import Status
from dbgpt.component import ComponentType, SystemApp
from dbgpt.configs.model_config import BENCHMARK_DATA_ROOT_PATH
from dbgpt.core import LLMClient
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.storage.metadata import BaseDao
from dbgpt.util import PaginationResult, get_or_create_event_loop
from dbgpt_serve.evaluate.service.benchmark.task.benchmark_agent_task import (
    BenchmarkAgentTask,
)
from dbgpt_serve.evaluate.service.benchmark.task.benchmark_llm_task import (
    BenchmarkLLMTask,
)

from ....core import BaseService
from ....prompt.service.service import Service as PromptService
from ....rag.service.service import Service as RagService
from ....rag.storage_manager import StorageManager
from ...api.schemas import (
    BenchmarkServeResponse,
    EvaluateServeRequest,
    EvaluateServeResponse,
    EvaluationScene,
    StorageType,
)
from ...config import ServeConfig
from ...models.models import ServeDao, ServeEntity
from ..fetchdata.benchmark_data_manager import get_benchmark_manager
from .data_compare_service import DataCompareService
from .file_parse_service import ExcelFileParseService
from .models import (
    BaseInputModel,
    BenchmarkDataSets,
    BenchmarkExecuteConfig,
    BenchmarkInvokeType,
    BenchmarkModeTypeEnum,
    BenchmarkTaskResult,
    ContentTypeEnum,
    FileParseTypeEnum,
    InputType,
    OutputType,
)
from .user_input_execute_service import UserInputExecuteService

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=5)

BENCHMARK_SERVICE_COMPONENT_NAME = "dbgpt_serve_evaluate_benchmark_service"

STANDARD_BENCHMARK_FILE_PATH = os.path.join(
    BENCHMARK_DATA_ROOT_PATH,
    "2025_07_27_public_500_standard_benchmark_question_list.xlsx",
)

BENCHMARK_OUTPUT_RESULT_PATH = os.path.join(BENCHMARK_DATA_ROOT_PATH, "result")


def get_rag_service(system_app) -> RagService:
    return system_app.get_component("dbgpt_rag_service", RagService)


def get_prompt_service(system_app) -> PromptService:
    return system_app.get_component("dbgpt_serve_prompt_service", PromptService)


class BenchmarkService(
    BaseService[ServeEntity, EvaluateServeRequest, EvaluateServeResponse]
):
    """The benchmark service class for Evaluate"""

    name = BENCHMARK_SERVICE_COMPONENT_NAME
    batch_lock = threading.RLock()

    def __init__(
        self, system_app: SystemApp, config: ServeConfig, dao: Optional[ServeDao] = None
    ):
        self._system_app = system_app
        self._serve_config: ServeConfig = config
        self._dao: ServeDao = dao
        super().__init__(system_app)
        self.rag_service = get_rag_service(system_app)
        self.prompt_service = get_prompt_service(system_app)
        self._file_parse_type = FileParseTypeEnum.EXCEL

        fps = ExcelFileParseService()
        dcs = DataCompareService()
        self.user_input_execute_service = UserInputExecuteService(fps, dcs)

        self.trigger_executor = ThreadPoolExecutor(
            max_workers=5, thread_name_prefix="benchmark-fileWrite"
        )

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._dao = self._dao or ServeDao(self._serve_config)
        self._system_app = system_app

    @property
    def storage_manager(self):
        return StorageManager.get_instance(self._system_app)

    @property
    def dao(self) -> BaseDao[ServeEntity, EvaluateServeRequest, EvaluateServeResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    @property
    def llm_client(self) -> LLMClient:
        worker_manager = self._system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return DefaultLLMClient(worker_manager, True)

    def create_benchmark_task(
        self,
        config: BenchmarkExecuteConfig,
        evaluate_code: str,
        scene_key: str,
        scene_value: str,
        input_file_path: str,
        output_file_path: str,
    ) -> bool:
        """
        Save the benchmark task to the database

        Args:
            config: Benchmark execute config
            evaluate_code: Evaluation code
            scene_key: Scene key
            scene_value: Scene value
            input_file_path: Input file path
            output_file_path: Output file path
            model_list: Model list
        """
        try:
            # 构建请求对象
            request_data = EvaluateServeRequest(
                evaluate_code=evaluate_code,
                scene_key=scene_key,
                scene_value=scene_value,
                datasets_name=os.path.basename(input_file_path)
                if input_file_path
                else None,
                datasets=None,
                storage_type=StorageType.FILE.value,
                parallel_num=1,
                state=Status.RUNNING.value,
                result=output_file_path,
                context={
                    "benchmark_config": json.dumps(
                        config.to_dict(), ensure_ascii=False
                    ),
                },
                user_id=None,
                user_name=None,
                sys_code="benchmark_system",
            )

            response = self.create(request_data)
            logger.info(
                f"Successfully saved benchmark task to database: "
                f"evaluate_code={evaluate_code}, scene_key={scene_key}, "
                f"scene_value={scene_value}, response: {response}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to save benchmark task to database: {e}, "
                f"evaluate_code={evaluate_code}, scene_key={scene_key}, "
                f"scene_value={scene_value}"
            )
            return False

    def _generate_output_file_full_path(
        self, output_file_path: str, evaluate_code: str
    ) -> str:
        """
        Generate the complete output file path,
        including the evaluate_code subfolder and default filename

        Args:
            output_file_path: Base path of the output file
            evaluate_code: Evaluation code, used as subfolder name

        Returns:
            str: Complete output file path
        """
        if not output_file_path or not evaluate_code:
            return output_file_path

        base_path = Path(output_file_path)
        output_base_file_name = (
            f"{datetime.now().strftime('%Y%m%d%H%M')}_multi_round_benchmark_result.xlsx"
        )
        new_path = base_path / evaluate_code / output_base_file_name
        return str(new_path)

    async def run_dataset_benchmark(
        self,
        evaluate_code: str,
        scene_key: str,
        scene_value: str,
        input_file_path: str,
        output_file_path: str,
        model_list: List[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        benchmark_type: Optional[str],
        api_url: Optional[str],
        http_method: Optional[str],
        headers: Optional[dict],
        parse_strategy: Optional[str],
        response_mapping: Optional[dict],
    ) -> List[BenchmarkTaskResult[OutputType]]:
        """
        Run the dataset benchmark
        """
        logger.info(
            f"Run dataset benchmark, evaluate_code: {evaluate_code},"
            f" scene_key: {scene_key}, scene_value: {scene_value},"
            f" input_file_path: {input_file_path}, output_file_path: {output_file_path}"
        )
        if not input_file_path:
            input_file_path = STANDARD_BENCHMARK_FILE_PATH
        if not evaluate_code:
            evaluate_code = uuid.uuid4().hex
        if not output_file_path:
            output_file_path = BENCHMARK_OUTPUT_RESULT_PATH
        if not scene_key:
            scene_key = EvaluationScene.DATASET.value

        output_file_path = self._generate_output_file_full_path(
            output_file_path, evaluate_code
        )

        config = await self._build_benchmark_config(
            model_list,
            output_file_path,
            evaluate_code,
            scene_key,
            temperature,
            max_tokens,
            benchmark_type,
            api_url,
            http_method,
            headers,
            parse_strategy,
            response_mapping,
        )
        logger.info(f"run benchmark with benchmarkConfig={config}")
        start_time = time.time()

        # save benchmark task
        self.create_benchmark_task(
            config,
            evaluate_code,
            scene_key,
            scene_value,
            input_file_path,
            output_file_path,
        )

        # Priority: load Falcon github benchmark dataset
        try:
            manager = get_benchmark_manager(self._system_app)
            await manager.load_data()
            logger.info(
                f"Benchmark dataset loaded from {manager._config.repo_url} "
                f"dir={manager._config.data_dir}"
            )
        except Exception as e:
            logger.error(
                f"Failed to load Falcon benchmark dataset before run task: {e}"
            )
            cost_time = int(time.time() - start_time)
            self._update_benchmark_task_status(
                evaluate_code, Status.FAILED.value, cost_time, error_message=str(e)
            )
            raise e

        result_list = []
        try:
            # read input file
            input_list: List[BaseInputModel] = (
                self.user_input_execute_service.read_input_file(input_file_path)
            )

            for i in range(1, config.round_time + 1):
                round_result_list: List[BenchmarkTaskResult[OutputType]] = []

                llm_index = 0
                for llm_code, thread_num in config.llm_thread_map.items():
                    # 每个llm_code对应的偏移量：llm_index * input_list长度
                    offset = len(input_list) * llm_index

                    llm_result = BenchmarkTaskResult[OutputType]()
                    try:
                        llm_result = self.batch_execute(
                            config,
                            input_list,
                            llm_code,
                            thread_num,
                            i,
                            output_file_path,
                            offset,
                        )
                    except Exception as e:
                        logger.error(f"batch execute error! {e}, llm_code: {llm_code}")

                    if llm_result is not None:
                        round_result_list.append(llm_result)
                        llm_index += 1

                self.post_dispatch(
                    i,
                    config,
                    input_list,
                    round_result_list,
                    input_file_path,
                    output_file_path,
                )
                result_list.extend(round_result_list)

            cost_time = int(time.time() - start_time)
            self._update_benchmark_task_status(
                evaluate_code, Status.COMPLETE.value, cost_time
            )
        except Exception as e:
            logger.error(
                f"Benchmark execution failed: {e}, evaluate_code: {evaluate_code}"
            )
            cost_time = int(time.time() - start_time)
            self._update_benchmark_task_status(
                evaluate_code, Status.FAILED.value, cost_time, error_message=str(e)
            )

        logger.info(
            f"Benchmark task completed successfully for evaluate_code:"
            f" {evaluate_code}, output_file_path: {output_file_path}, "
            f"benchmark task costTime: {cost_time}"
        )
        return result_list

    def _parse_http_method(self, http_method: Optional[str]):
        from .models import HttpMethod

        if not http_method:
            return HttpMethod.POST

        try:
            return HttpMethod(http_method.upper())
        except ValueError:
            logger.warning(f"Invalid HTTP method: {http_method}, using default POST")
            return HttpMethod.POST

    def _parse_response_strategy(self, parse_strategy: Optional[str]):
        from .models import ResponseParseStrategy

        if not parse_strategy:
            return ResponseParseStrategy.JSON_PATH

        try:
            return ResponseParseStrategy(parse_strategy.upper())
        except ValueError:
            logger.warning(
                f"Invalid parse strategy: {parse_strategy}, using default JSON_PATH"
            )
            return ResponseParseStrategy.JSON_PATH

    def _create_agent_config(
        self,
        api_url: str,
        http_method: Optional[str],
        headers: Optional[dict],
        parse_strategy: Optional[str],
        response_mapping: Optional[dict],
    ):
        from .models import AgentApiConfig

        http_method_enum = self._parse_http_method(http_method)
        parse_strategy_enum = self._parse_response_strategy(parse_strategy)

        agent_config = AgentApiConfig(
            api_url=api_url,
            http_method=http_method_enum,
            headers=headers or {},
            parse_strategy=parse_strategy_enum,
            response_mapping=response_mapping,
        )
        return agent_config

    async def _build_benchmark_config(
        self,
        model_list,
        output_file_path,
        evaluate_code,
        scene_key,
        temperature,
        max_tokens,
        benchmark_type,
        api_url,
        http_method,
        headers,
        parse_strategy,
        response_mapping,
    ) -> BenchmarkExecuteConfig:
        config = BenchmarkExecuteConfig(
            benchmark_mode_type=BenchmarkModeTypeEnum.EXECUTE,
            standard_file_path=STANDARD_BENCHMARK_FILE_PATH,
            output_file_path=output_file_path,
            content_type=ContentTypeEnum.SQL,
            round_time=1,
            thread_num=1,
            execute_llm_result=True,
            invoke_llm=True,
            compare_result_enable=True,
            file_parse_type=self._file_parse_type,
            evaluate_code=evaluate_code,
            scene_key=scene_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if benchmark_type == BenchmarkInvokeType.AGENT.name:
            config.invoke_type = BenchmarkInvokeType.AGENT
            config.llm_thread_map = {"agent": config.thread_num}
            config.agent_config = self._create_agent_config(
                api_url, http_method, headers, parse_strategy, response_mapping
            )
        else:
            config.invoke_type = BenchmarkInvokeType.LLM
            config.llm_thread_map = {model: 1 for model in model_list}

        return config

    def _format_prompt_template(
        self,
        prompt: str,
    ) -> str:
        try:
            dialect = self._get_database_dialect()
            format_params = {
                "dialect": dialect,
            }
            return prompt.format(**format_params)
        except Exception as e:
            logger.warning(f"Failed to format prompt template: {e}. ")
            return prompt

    def _get_database_dialect(self) -> str | None:
        try:
            db_connector = get_benchmark_manager().get_connector()
            if db_connector and hasattr(db_connector, "dialect"):
                return db_connector.dialect
        except Exception as e:
            logger.warning(f"Failed to get database dialect: {e}")
        return None

    def _update_benchmark_task_status(
        self,
        evaluate_code: str,
        status: str,
        cost_time: int,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update the status and execution time information of the benchmark task

        Args:
            evaluate_code: Evaluation code
            status: Task status (Status.COMPLETE.value or Status.FAILED.value)
            cost_time: Execution time (in seconds)
            error_message: Error message
        """
        try:
            running_info = {"cost_time": cost_time}

            # 获取现有的context数据并保留原有结构
            context_data = {}
            existing_entity: EvaluateServeResponse = self.dao.get_one(
                {"evaluate_code": evaluate_code}
            )
            if existing_entity and existing_entity.context:
                try:
                    if isinstance(existing_entity.context, dict):
                        context_data = existing_entity.context.copy()
                    elif isinstance(existing_entity.context, str):
                        existing_context = json.loads(existing_entity.context)
                        if isinstance(existing_context, dict):
                            context_data = existing_context.copy()
                except (json.JSONDecodeError, TypeError):
                    context_data = {}

            context_data["benchmark_running_info"] = json.dumps(
                running_info, ensure_ascii=False
            )

            update_request = EvaluateServeRequest(
                state=status,
                context=context_data,
                log_info=error_message,
            )
            self.dao.update({"evaluate_code": evaluate_code}, update_request)
            logger.info(
                f"Successfully updated benchmark task status to {status} "
                f"with cost_time: {cost_time}s, evaluate_code: {evaluate_code}"
            )
        except Exception as e:
            logger.error(
                f"Failed to update benchmark task status to {status}: {e}, "
                f"evaluate_code: {evaluate_code}"
            )

    def batch_execute(
        self,
        config: BenchmarkExecuteConfig,
        inputs: List[InputType],
        llm_code: str,
        thread_num: int,
        round_id: int,
        output_file_path: str,
        offset: int,
    ) -> BenchmarkTaskResult[OutputType]:
        """
        Batch execute the benchmark Task with LLM
        """
        result = BenchmarkTaskResult[OutputType]()
        result.trace_id = uuid.uuid4().hex
        result.task_id = (
            config.evaluate_code if config.evaluate_code else uuid.uuid4().hex
        )
        result.start_time = datetime.now()

        executor = ThreadPoolExecutor(
            max_workers=thread_num, thread_name_prefix="benchmark-USER_INPUT_EXECUTE"
        )

        output_sets = BenchmarkDataSets[OutputType]()
        output_list: List[OutputType] = []

        written_batches: set[int] = set()
        complete_map: Dict[int, OutputType] = {}

        # 线程锁，保证线程安全
        lock = threading.Lock()

        def execute_task(input_data: InputType):
            """task execution function"""
            try:
                input_data.llm_code = llm_code
                logger.info(
                    f"[benchmark_task]start executeBenchmark!"
                    f" question={input_data.question}"
                )

                start_time = time.time()
                loop = get_or_create_event_loop()
                output: OutputType = loop.run_until_complete(
                    self.execute(config, input_data)
                )
                cost_time = int(time.time() - start_time)

                output.cost_time = cost_time
                logger.info(
                    f"[benchmark_task]end executeBenchmark! serial_no={output.serialNo}"
                )

                with lock:
                    output_list.append(output)

                # 检查并触发批次处理
                self.check_and_trigger_batch(
                    output,
                    inputs,
                    round_id,
                    config,
                    output_file_path,
                    written_batches,
                    complete_map,
                    offset,
                )
            except Exception as e:
                logger.error(f"executeSingleTimeBenchmark error, error: {e}")

        # 提交所有任务
        futures = [executor.submit(execute_task, input_data) for input_data in inputs]

        # 等待所有任务完成
        for future in futures:
            future.result()

        executor.shutdown(wait=True)

        output_sets.data_list = output_list
        result.benchmark_data_sets = output_sets
        return result

    async def execute(
        self, config: BenchmarkExecuteConfig, input: InputType
    ) -> Union[OutputType, None]:
        """
        Execute Benchmark Task (LLM or Agent)
        """
        try:
            # 1. 组装评测输入
            if input.prompt is None:
                raise Exception("benchmark datasets not have prompt template!")

            # format prompt template
            input.prompt = self._format_prompt_template(input.prompt)

            # 2. 执行评测
            if config.invoke_type == BenchmarkInvokeType.AGENT:
                agent_config = config.agent_config
                if not agent_config:
                    raise Exception(
                        f"Agent API configuration not found for agent: {input.llm_code}"
                    )
                benchmark_agent_task = BenchmarkAgentTask(
                    api_config=agent_config,
                )

                # 调用 Agent 执行评测
                response = await benchmark_agent_task.invoke_agent(
                    prompt=input.prompt,
                    question=input.question,
                    knowledge=input.knowledge,
                    self_define_tags=input.self_define_tags,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
            else:
                # LLM 模式：调用本地 LLM Client
                benchmark_llm_task_service = BenchmarkLLMTask(
                    llm_client=self.llm_client, model_name=input.llm_code
                )

                response = await benchmark_llm_task_service.invoke_llm(
                    prompt=input.prompt,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )

            # 3. 组装评测输出
            return await self.user_input_execute_service.build_output(
                config, input, response
            )
        except Exception as e:
            logger.error(f"execute benchmark error!  error: {e}")
        return None

    def check_and_trigger_batch(
        self,
        output: OutputType,
        inputs: List[BaseInputModel],
        round_id: int,
        config: BenchmarkExecuteConfig,
        output_file_path: str,
        written_batches: set,
        complete_map: Dict[int, OutputType],
        offset: int,
    ):
        """
        Check if all tasks in the current batch are completed
        and trigger batch processing.
        """
        with self.batch_lock:
            complete_map[output.serialNo] = output
            batch_size = 10

            # 查找当前任务的索引
            task_index = -1
            for i in range(len(inputs)):
                if inputs[i].serial_no == output.serialNo:
                    task_index = i
                    break

            batch_index = task_index // batch_size

            # 避免重复写入
            if batch_index in written_batches:
                return

            # 计算批次范围
            batch_start = batch_index * batch_size
            batch_end = min(len(inputs), (batch_index + 1) * batch_size)

            # 检查当前批次是否全部完成
            is_batch_complete = True
            batch_outputs: List[OutputType] = []

            for i in range(batch_start, batch_end):
                serial_no = inputs[i].serial_no
                if serial_no not in complete_map:
                    is_batch_complete = False
                    break
                batch_outputs.append(complete_map[serial_no])

            if is_batch_complete:
                # 触发异步任务并写入
                def batch_write_task():
                    try:
                        # 执行写入逻辑
                        batch_outputs.sort(key=lambda x: x.serialNo)
                        self.user_input_execute_service.write_output_file(
                            output_file_path,
                            round_id,
                            config,
                            inputs,
                            batch_outputs,
                            batch_start,
                            offset,
                        )
                    except Exception as e:
                        logger.error(f"Batch write error: {e}")

                batch_write_task()
                written_batches.add(batch_index)

    def post_dispatch(
        self,
        i: int,
        config: BenchmarkExecuteConfig,
        input_list: List[BaseInputModel],
        output_list: List[BenchmarkTaskResult[OutputType]],
        input_file_path: str,
        output_file_path: str,
    ):
        """
        Post dispatch processing standard result compare LLM execute result
        and write compare result to file
        """
        for j, output_result in enumerate(output_list):
            self.user_input_execute_service.post_dispatch(
                i,
                config,
                input_list,
                None,
                output_result.benchmark_data_sets.data_list,
                input_file_path,
                output_file_path,
            )

    def get_list_by_page(
        self, request: EvaluateServeRequest, page: int, page_size: int
    ) -> PaginationResult[BenchmarkServeResponse]:
        """Get a list of Evaluate entities by page

        Args:
            request (EvaluateServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            PaginationResult[BenchmarkServeResponse]: The response
        """
        query_request = request
        original_result = self.dao.get_list_page(
            query_request, page, page_size, ServeEntity.id.name
        )

        benchmark_items = []
        for item in original_result.items:
            benchmark_response = self._convert_to_benchmark_response(item)
            benchmark_items.append(benchmark_response)

        return PaginationResult[BenchmarkServeResponse](
            items=benchmark_items,
            total_count=original_result.total_count,
            total_pages=original_result.total_pages,
            page=original_result.page,
            page_size=original_result.page_size,
        )

    def _convert_to_benchmark_response(
        self, evaluate_response: EvaluateServeResponse
    ) -> BenchmarkServeResponse:
        """Convert EvaluateServeResponse to BenchmarkServeResponse

        Args:
            evaluate_response: The original EvaluateServeResponse

        Returns:
            BenchmarkServeResponse: The converted response
        """
        cost_time = None
        model_list = None
        parallel_num = None
        round_time = None

        # parse context data
        if evaluate_response.context:
            try:
                context_data = evaluate_response.context
                if isinstance(context_data, str):
                    context_data = json.loads(context_data)

                if "benchmark_config" in context_data:
                    benchmark_config_str = context_data["benchmark_config"]
                    if isinstance(benchmark_config_str, str):
                        benchmark_config = json.loads(benchmark_config_str)
                        if "llm_thread_map" in benchmark_config:
                            llm_thread_map = benchmark_config["llm_thread_map"]
                            if isinstance(llm_thread_map, dict):
                                model_list = list(llm_thread_map.keys())
                        if "thread_num" in benchmark_config:
                            parallel_num = benchmark_config["thread_num"]
                        if "round_time" in benchmark_config:
                            round_time = benchmark_config["round_time"]

                if "benchmark_running_info" in context_data:
                    running_info_str = context_data["benchmark_running_info"]
                    if isinstance(running_info_str, str):
                        running_info = json.loads(running_info_str)
                        if "cost_time" in running_info:
                            cost_time = running_info["cost_time"]

            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Failed to parse context data: {e}")

        return BenchmarkServeResponse(
            evaluate_code=evaluate_response.evaluate_code,
            scene_key=evaluate_response.scene_key,
            scene_value=evaluate_response.scene_value,
            datasets_name="Falcon评测集",
            input_file_path=evaluate_response.datasets_name,
            output_file_path=evaluate_response.result,
            model_list=model_list,
            context=evaluate_response.context,
            user_name=evaluate_response.user_name,
            user_id=evaluate_response.user_id,
            sys_code=evaluate_response.sys_code,
            parallel_num=parallel_num,
            state=evaluate_response.state,
            temperature=None,
            max_tokens=None,
            log_info=evaluate_response.log_info,
            gmt_create=evaluate_response.gmt_create,
            gmt_modified=evaluate_response.gmt_modified,
            cost_time=cost_time,
            round_time=round_time,
        )

    async def get_benchmark_file_stream(
        self, evaluate_code: str
    ) -> Tuple[str, io.BytesIO]:
        """Get benchmark result file stream for download

        Args:
            evaluate_code (str): The evaluation code

        Returns:
            Tuple[str, io.BytesIO]: File name and file stream

        Raises:
            Exception: If evaluation record not found or file not exists
        """
        if not evaluate_code:
            raise Exception("evaluate_code is required")

        # 1. 根据evaluate_code查询评测信息
        try:
            entity = self.dao.get_one({"evaluate_code": evaluate_code})
            if not entity:
                raise Exception(
                    f"Evaluation record not found for code: {evaluate_code}"
                )
        except Exception as e:
            logger.error(f"Failed to query evaluation record: {e}")
            raise Exception(f"Failed to query evaluation record: {str(e)}")

        # 2. 根据result的文件路径拿到文件
        file_path = entity.result
        if not file_path:
            raise Exception(
                f"No result file path found for evaluate_code: {evaluate_code}"
            )

        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise Exception(f"Result file not found: {file_path}")

        try:
            # 读取文件内容到内存
            with open(file_path, "rb") as file:
                file_content = file.read()

            # 创建字节流
            file_stream = io.BytesIO(file_content)

            # 获取文件名
            file_name = os.path.basename(file_path)

            logger.info(f"Successfully prepared file stream for download: {file_name}")
            return file_name, file_stream

        except Exception as e:
            logger.error(f"Failed to read result file {file_path}: {e}")
            raise Exception(f"Failed to read result file: {str(e)}")

    def get_benchmark_by_evaluate_code(self, evaluate_code: str):
        if not evaluate_code:
            return None
        try:
            entity = self.dao.get_one({"evaluate_code": evaluate_code})
            if not entity:
                return None
            return entity
        except Exception as e:
            logger.error(
                f"Failed to query evaluation record by evaluate_code:"
                f" {evaluate_code}, error: {e}"
            )
            raise Exception(f"Failed to query evaluation record: {str(e)}")
