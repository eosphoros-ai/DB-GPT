import json
import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import ComponentType, SystemApp
from dbgpt.model.cluster import BaseModelController, WorkerManager, WorkerManagerFactory
from dbgpt_serve.core import Result
from dbgpt_serve.evaluate.api.schemas import (
    BenchmarkServeRequest,
    BuildDemoRequest,
    EvaluateServeRequest,
    ExecuteDemoRequest,
)
from dbgpt_serve.evaluate.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.evaluate.db.benchmark_db import BenchmarkResultDao
from dbgpt_serve.evaluate.service.benchmark.data_compare_service import (
    DataCompareService,
)
from dbgpt_serve.evaluate.service.benchmark.file_parse_service import FileParseService
from dbgpt_serve.evaluate.service.benchmark.models import (
    BenchmarkExecuteConfig,
    BenchmarkModeTypeEnum,
)
from dbgpt_serve.evaluate.service.benchmark.user_input_execute_service import (
    UserInputExecuteService,
)
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


@router.get("/benchmark/list_results", dependencies=[Depends(check_api_key)])
async def list_compare_runs(limit: int = 50, offset: int = 0):
    dao = BenchmarkResultDao()
    rows = dao.list_summaries(limit=limit, offset=offset)
    result = []
    for s in rows:
        result.append(
            {
                "id": s.id,
                "roundId": s.round_id,
                "outputPath": s.output_path,
                "right": s.right,
                "wrong": s.wrong,
                "failed": s.failed,
                "exception": s.exception,
                "gmtCreated": s.gmt_created.isoformat() if s.gmt_created else None,
            }
        )
    return Result.succ(result)


@router.get("/benchmark/result/{summary_id}", dependencies=[Depends(check_api_key)])
async def get_compare_run_detail(summary_id: int, limit: int = 200, offset: int = 0):
    dao = BenchmarkResultDao()
    s = dao.get_summary_by_id(summary_id)
    if not s:
        raise HTTPException(status_code=404, detail="compare run not found")
    compares = dao.list_compare_by_round_and_path(
        s.round_id, s.output_path, limit=limit, offset=offset
    )
    detail = {
        "id": s.id,
        "roundId": s.round_id,
        "outputPath": s.output_path,
        "summary": {
            "right": s.right,
            "wrong": s.wrong,
            "failed": s.failed,
            "exception": s.exception,
        },
        "items": [
            {
                "id": r.id,
                "serialNo": r.serial_no,
                "analysisModelId": r.analysis_model_id,
                "question": r.question,
                "prompt": r.prompt,
                "standardAnswerSql": r.standard_answer_sql,
                "llmOutput": r.llm_output,
                "executeResult": json.loads(r.execute_result)
                if r.execute_result
                else None,
                "errorMsg": r.error_msg,
                "compareResult": r.compare_result,
                "isExecute": r.is_execute,
                "llmCount": r.llm_count,
                "gmtCreated": r.gmt_created.isoformat() if r.gmt_created else None,
            }
            for r in compares
        ],
    }
    return Result.succ(detail)


@router.post("/execute_benchmark_task")
async def execute_benchmark_task(
    request: BenchmarkServeRequest,
    service: BenchmarkService = Depends(get_benchmark_service),
) -> Result:
    """execute benchmark task

    Args:
        request (EvaluateServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(
        await service.run_dataset_benchmark(
            request.evaluate_code,
            request.scene_key,
            request.scene_value,
            request.input_file_path,
            request.output_file_path,
            request.model_list,
        )
    )


@router.get("/benchmark/datasets", dependencies=[Depends(check_api_key)])
async def list_benchmark_datasets():
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


@router.get("/benchmark/datasets/{table}/rows", dependencies=[Depends(check_api_key)])
async def get_benchmark_table_rows(table: str, limit: int = 10):
    manager = get_benchmark_manager(global_system_app)
    info = await manager.get_table_info()
    if table not in info:
        raise HTTPException(status_code=404, detail=f"table '{table}' not found")
    sql = f'SELECT * FROM "{table}" LIMIT :limit'
    rows = await manager.query(sql, {"limit": limit})
    return Result.succ({"table": table, "limit": limit, "rows": rows})


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    system_app.register(BenchmarkService, config=config)
    global_system_app = system_app
