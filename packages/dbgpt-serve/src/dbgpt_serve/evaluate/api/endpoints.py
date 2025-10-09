import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import ComponentType, SystemApp
from dbgpt.model.cluster import BaseModelController, WorkerManager, WorkerManagerFactory
from dbgpt_serve.core import Result
from dbgpt_serve.evaluate.api.schemas import EvaluateServeRequest, BuildDemoRequest, ExecuteDemoRequest
from dbgpt_serve.evaluate.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.evaluate.service.service import Service
from dbgpt_serve.evaluate.db.benchmark_db import BenchmarkResultDao
import json
from dbgpt_serve.evaluate.service.benchmark.file_parse_service import FileParseService
from dbgpt_serve.evaluate.service.benchmark.data_compare_service import DataCompareService
from dbgpt_serve.evaluate.service.benchmark.user_input_execute_service import UserInputExecuteService
from dbgpt_serve.evaluate.service.benchmark.models import BenchmarkExecuteConfig, BenchmarkModeTypeEnum
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import get_benchmark_manager

from ...prompt.service.service import Service as PromptService

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None
logger = logging.getLogger(__name__)


def get_service() -> Service:
    """Get the service instance"""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


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


@router.get("/benchmark/compare", dependencies=[Depends(check_api_key)])
async def list_benchmark_compare(
    round_id: int,
    limit: int = 50,
    offset: int = 0,
):
    dao = BenchmarkResultDao()
    rows = dao.list_compare_by_round(round_id, limit=limit, offset=offset)
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "round_id": r.round_id,
            "mode": r.mode,
            "serialNo": r.serial_no,
            "analysisModelId": r.analysis_model_id,
            "question": r.question,
            "selfDefineTags": r.self_define_tags,
            "prompt": r.prompt,
            "standardAnswerSql": r.standard_answer_sql,
            "llmOutput": r.llm_output,
            "executeResult": json.loads(r.execute_result) if r.execute_result else None,
            "errorMsg": r.error_msg,
            "compareResult": r.compare_result,
            "isExecute": r.is_execute,
            "llmCount": r.llm_count,
            "outputPath": r.output_path,
            "gmtCreated": r.gmt_created.isoformat() if r.gmt_created else None,
        })
    return Result.succ(result)


@router.post("/benchmark/run_build", dependencies=[Depends(check_api_key)])
async def benchmark_run_build(req: BuildDemoRequest):
    fps = FileParseService()
    dcs = DataCompareService()
    svc = UserInputExecuteService(fps, dcs)

    inputs = fps.parse_input_sets(req.input_file_path)
    left = fps.parse_llm_outputs(req.left_output_file_path)
    right = fps.parse_llm_outputs(req.right_output_file_path)

    config = BenchmarkExecuteConfig(
        benchmarkModeType=BenchmarkModeTypeEnum.BUILD,
        compareResultEnable=True,
        standardFilePath=None,
        compareConfig=req.compare_config or {"check": "FULL_TEXT"},
    )

    svc.post_dispatch(
        round_id=req.round_id,
        config=config,
        inputs=inputs,
        left_outputs=left,
        right_outputs=right,
        input_file_path=req.input_file_path,
        output_file_path=req.right_output_file_path,
    )

    summary = fps.summary_and_write_multi_round_benchmark_result(
        req.right_output_file_path, req.round_id
    )
    return Result.succ({"summary": json.loads(summary)})


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app


@router.get("/benchmark/datasets", dependencies=[Depends(check_api_key)])
async def list_benchmark_datasets():
    manager = get_benchmark_manager(global_system_app)
    info = await manager.get_table_info()
    result = [
        {"name": name, "rowCount": meta.get("row_count", 0), "columns": meta.get("columns", [])}
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


@router.post("/benchmark/run_execute", dependencies=[Depends(check_api_key)])
async def benchmark_run_execute(req: ExecuteDemoRequest):
    fps = FileParseService()
    dcs = DataCompareService()
    svc = UserInputExecuteService(fps, dcs)

    inputs = fps.parse_input_sets(req.input_file_path)
    right = fps.parse_llm_outputs(req.right_output_file_path)

    config = BenchmarkExecuteConfig(
        benchmarkModeType=BenchmarkModeTypeEnum.EXECUTE,
        compareResultEnable=True,
        standardFilePath=req.standard_file_path,
        compareConfig=req.compare_config,
    )

    svc.post_dispatch(
        round_id=req.round_id,
        config=config,
        inputs=inputs,
        left_outputs=[],
        right_outputs=right,
        input_file_path=req.input_file_path,
        output_file_path=req.right_output_file_path,
    )

    summary = fps.summary_and_write_multi_round_benchmark_result(
        req.right_output_file_path, req.round_id
    )
    return Result.succ({"summary": json.loads(summary)})
