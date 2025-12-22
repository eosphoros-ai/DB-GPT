import asyncio
import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.agent.core.schema import Status
from dbgpt.component import ComponentType, SystemApp
from dbgpt.model.cluster import BaseModelController, WorkerManager, WorkerManagerFactory
from dbgpt_serve.core import Result
from dbgpt_serve.evaluate.api.schemas import (
    BenchmarkServeRequest,
    EvaluateServeRequest,
)
from dbgpt_serve.evaluate.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.evaluate.db.benchmark_db import BenchmarkResultDao
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import (
    get_benchmark_manager,
)
from dbgpt_serve.evaluate.service.service import Service

from ...prompt.service.service import Service as PromptService
from ..service.benchmark.benchmark_service import (
    BENCHMARK_SERVICE_COMPONENT_NAME,
    BenchmarkService,
)

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None
logger = logging.getLogger(__name__)


def _run_benchmark_task_sync(service: BenchmarkService, request: BenchmarkServeRequest):
    """同步执行benchmark任务的辅助函数，用于在后台任务中运行"""
    try:
        # 创建新的事件循环来运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                service.run_dataset_benchmark(
                    evaluate_code=request.evaluate_code,
                    scene_key=request.scene_key,
                    scene_value=request.scene_value,
                    input_file_path=request.input_file_path,
                    output_file_path=request.output_file_path,
                    model_list=request.model_list,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    benchmark_type=request.benchmark_type,
                    api_url=request.api_url,
                    http_method=request.http_method,
                    headers=request.headers,
                    parse_strategy=request.parse_strategy,
                    response_mapping=request.response_mapping,
                )
            )
            logger.info(f"Benchmark task run sync finish, request: {request}")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Benchmark task failed for request: {request}, error: {str(e)}")


def get_service() -> Service:
    """Get the service instance"""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


def get_benchmark_service() -> BenchmarkService:
    """Get the benchmark service instance"""
    return global_system_app.get_component(
        BENCHMARK_SERVICE_COMPONENT_NAME, BenchmarkService
    )


def get_prompt_service() -> PromptService:
    return global_system_app.get_component("dbgpt_serve_prompt_service", PromptService)


def get_worker_manager() -> WorkerManager:
    worker_manager = global_system_app.get_component(
        ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
    ).create()
    return worker_manager


def get_model_controller() -> BaseModelController:
    controller = global_system_app.get_component(
        ComponentType.MODEL_CONTROLLER, BaseModelController
    )
    return controller


get_bearer_token = HTTPBearer(auto_error=False)


@cache
def _parse_api_keys(api_keys: str) -> List[str]:
    """Parse the string api keys to a list

    Args:
        api_keys (str): The string api keys

    Returns:
        List[str]: The list of api keys
    """
    if not api_keys:
        return []
    return [key.strip() for key in api_keys.split(",")]


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    service: Service = Depends(get_service),
) -> Optional[str]:
    """Check the api key

    If the api key is not set, allow all.

    Your can pass the token in you request header like this:

    .. code-block:: python

        import requests

        client_api_key = "your_api_key"
        headers = {"Authorization": "Bearer " + client_api_key}
        res = requests.get("http://test/hello", headers=headers)
        assert res.status_code == 200

    """
    if service.config.api_keys:
        api_keys = _parse_api_keys(service.config.api_keys)
        if auth is None or (token := auth.credentials) not in api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    else:
        # api_keys not set; allow all
        return None


@router.get("/health", dependencies=[Depends(check_api_key)])
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.get("/scenes")
async def get_scenes():
    scene_list = [{"recall": "召回评测"}, {"app": "应用评测"}]

    return Result.succ(scene_list)


@router.post("/evaluation")
async def evaluation(
    request: EvaluateServeRequest,
    service: Service = Depends(get_service),
) -> Result:
    """Evaluate results by the scene

    Args:
        request (EvaluateServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(
        await service.run_evaluation(
            request.scene_key,
            request.scene_value,
            request.datasets,
            request.context,
            request.evaluate_metrics,
        )
    )


@router.get("/benchmark/result/{evaluate_code}", dependencies=[Depends(check_api_key)])
async def get_compare_run_detail(
    evaluate_code: str, service: BenchmarkService = Depends(get_benchmark_service)
):
    dao = BenchmarkResultDao()
    summaries = dao.list_summaries_by_task(evaluate_code, limit=10000, offset=0)
    if not summaries:
        return Result.succ(
            {
                "evaluate_code": evaluate_code,
                "summaries": [],
                "metrics": {},
                "cotTokens": {"total": 0, "byModel": {}},
            }
        )
    entity = service.get_benchmark_by_evaluate_code(evaluate_code)

    detail_list = []
    total_counts = {"right": 0, "wrong": 0, "failed": 0, "exception": 0}
    round_ids = set()
    for s in summaries:
        r, w, f, e = s.right, s.wrong, s.failed, s.exception
        denom_exec = max(r + w + f + e, 1)
        accuracy = r / denom_exec
        exec_rate = (r + w) / denom_exec
        total_counts["right"] += r
        total_counts["wrong"] += w
        total_counts["failed"] += f
        total_counts["exception"] += e
        round_ids.add(s.round_id)
        detail_list.append(
            {
                "roundId": s.round_id,
                "llmCode": getattr(s, "llm_code", None),
                "right": r,
                "wrong": w,
                "failed": f,
                "exception": e,
                "accuracy": accuracy,
                "execRate": exec_rate,
                "outputPath": s.output_path,
            }
        )

    return Result.succ(
        {
            "evaluate_code": evaluate_code,
            "scene_value": entity.scene_value if entity else None,
            "summaries": detail_list,
        }
    )


@router.post("/execute_benchmark_task", dependencies=[Depends(check_api_key)])
async def execute_benchmark_task(
    request: BenchmarkServeRequest,
    background_tasks: BackgroundTasks,
    service: BenchmarkService = Depends(get_benchmark_service),
) -> Result:
    """execute benchmark task

    Args:
        request (BenchmarkServeRequest): The request
        background_tasks (BackgroundTasks): FastAPI background tasks
        service (BenchmarkService): The service
    Returns:
        Result: The response
    """
    background_tasks.add_task(_run_benchmark_task_sync, service, request)

    # 立即返回成功响应
    return Result.succ(
        {"evaluate_code": request.evaluate_code, "status": Status.RUNNING.value}
    )


@router.get("/benchmark_task_list", dependencies=[Depends(check_api_key)])
async def benchmark_task_list(
    state: Optional[str] = Query(default=None, description="benchmark task state"),
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=20, description="page size"),
    service: BenchmarkService = Depends(get_benchmark_service),
) -> Result:
    """
    Query benchmark task list
    """
    request = EvaluateServeRequest(
        state=state,
    )
    return Result.succ(
        service.get_list_by_page(
            request,
            page,
            page_size,
        )
    )


@router.get("/benchmark/list_datasets", dependencies=[Depends(check_api_key)])
async def list_benchmark_datasets():
    manager = get_benchmark_manager(global_system_app)
    info = await manager.get_table_info()
    result = [{"dataset_id": "1", "name": "Falcon", "tableCount": len(info.items())}]
    return Result.succ(result)


@router.get("/benchmark/dataset/{dataset_id}", dependencies=[Depends(check_api_key)])
async def list_benchmark_dataset_tables(
    dataset_id: str, limit: int = 200, offset: int = 0
):
    if dataset_id == "1":
        manager = get_benchmark_manager(global_system_app)
        info = await manager.get_table_info()
        result = [
            {
                "name": name,
                "rowCount": meta.get("row_count", 0),
                "columns": meta.get("columns", []),
            }
            for name, meta in info.items()
        ]
        return Result.succ(result)
    else:
        return Result.succ("dataset not found")


@router.get(
    "/benchmark/dataset/{dataset_id}/{table}/rows",
    dependencies=[Depends(check_api_key)],
)
async def get_benchmark_table_rows(dataset_id: str, table: str, limit: int = 10):
    if dataset_id == "1":
        manager = get_benchmark_manager(global_system_app)
        info = await manager.get_table_info()
        if table not in info:
            raise HTTPException(status_code=404, detail=f"table '{table}' not found")
        sql = f'SELECT * FROM "{table}" LIMIT :limit'
        rows = await manager.query(sql, {"limit": limit})
        return Result.succ({"table": table, "limit": limit, "rows": rows})
    else:
        return Result.succ("dataset not found")


@router.get("/benchmark_result_download", dependencies=[Depends(check_api_key)])
async def download_benchmark_result(
    evaluate_code: Optional[str] = Query(default=None, description="evaluate code"),
    service: BenchmarkService = Depends(get_benchmark_service),
):
    """Download benchmark result file

    Args:
        evaluate_code: The evaluation code to identify the benchmark result
        service: The benchmark service instance

    Returns:
        StreamingResponse: File download response

    Raises:
        HTTPException: If evaluation code is missing or file not found
    """
    logger.info(f"download benchmark result: {evaluate_code}")

    if not evaluate_code:
        raise HTTPException(status_code=400, detail="evaluate_code is required")

    try:
        # 获取文件名和文件流
        file_name, file_stream = await service.get_benchmark_file_stream(evaluate_code)

        from urllib.parse import quote

        # 对文件名进行编码处理，支持中文和特殊字符
        encoded_filename = quote(file_name)

        # 返回文件下载响应
        return StreamingResponse(
            content=file_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''"
                f"{encoded_filename}; filename={encoded_filename}",
                "Content-Type": "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet",
            },
        )

    except Exception as e:
        logger.error(
            f"Failed to download benchmark result for {evaluate_code}: {str(e)}"
        )
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/benchmark/list_results", dependencies=[Depends(check_api_key)])
async def list_benchmark_tasks(limit: int = 50, offset: int = 0):
    dao = BenchmarkResultDao()
    tasks = dao.list_tasks(limit=limit, offset=offset)
    result = []
    for evaluate_code in tasks:
        summaries = dao.list_summaries_by_task(evaluate_code, limit=10000, offset=0)
        result.append(
            {
                "evaluate_code": evaluate_code,
                "summaries": [
                    {
                        "roundId": s.round_id,
                        "llmCode": getattr(s, "llm_code", None),
                        "right": s.right,
                        "wrong": s.wrong,
                        "failed": s.failed,
                        "exception": s.exception,
                        "outputPath": s.output_path,
                    }
                    for s in summaries
                ],
            }
        )
    return Result.succ(result)


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    system_app.register(BenchmarkService, config=config)
    global_system_app = system_app
