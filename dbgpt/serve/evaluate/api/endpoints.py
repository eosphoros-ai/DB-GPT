import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import ComponentType, SystemApp
from dbgpt.core.interface.evaluation import metric_manage
from dbgpt.model.cluster import BaseModelController, WorkerManager, WorkerManagerFactory
from dbgpt.rag.evaluation.answer import AnswerRelevancyMetric
from dbgpt.serve.core import Result
from dbgpt.serve.evaluate.api.schemas import (
    DatasetServeRequest,
    DatasetServeResponse,
    EvaluateServeRequest,
    EvaluateServeResponse,
)
from dbgpt.serve.evaluate.config import (
    SERVE_DATASET_SERVICE_COMPONENT_NAME,
    SERVE_SERVICE_COMPONENT_NAME,
)
from dbgpt.serve.evaluate.service.service import Service
from dbgpt.serve.evaluate.service.service_dataset import DatasetService
from dbgpt.util import PaginationResult

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


def get_dataset_service() -> DatasetService:
    return global_system_app.get_component(
        SERVE_DATASET_SERVICE_COMPONENT_NAME, DatasetService
    )


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


@router.get("/storage/types")
async def get_storage_types():
    storage_list = [{"oss": "oss存储"}, {"db": "db直接存储"}]

    return Result.succ(storage_list)


@router.get("/metrics")
async def get_metrics(
    scene_key: str,
    scene_value: str,
    prompt_service: PromptService = Depends(get_prompt_service),
    controller: WorkerManager = Depends(get_model_controller),
):
    metrics = metric_manage.all_metric_infos()
    for metric in metrics:
        if metric["name"] == AnswerRelevancyMetric.name:
            types = set()
            models = await controller.get_all_instances(healthy_only=True)
            for model in models:
                worker_name, worker_type = model.model_name.split("@")
                if worker_type == "llm" and worker_name not in [
                    "codegpt_proxyllm",
                    "text2sql_proxyllm",
                ]:
                    types.add(worker_name)
            metric["params"] = {
                "prompts": prompt_service.get_list({}),
                "models": list(types),
            }

    return Result.succ(metrics)


@router.post("/start")
async def evaluation_start(
    request: EvaluateServeRequest,
    service: Service = Depends(get_service),
) -> Result:
    return Result.succ(await service.new_evaluation(request))


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


@router.get(
    "/evaluations",
    response_model=Result[PaginationResult[EvaluateServeResponse]],
)
async def list_evaluations(
    filter_param: Optional[str] = Query(default=None, description="filter param"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=100, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[EvaluateServeResponse]]:
    """
    query evaluations
    Args:
        filter_param (str): The query filter param
        page (int): The page index
        page_size (int): The page size
    Returns:
        ServerResponse: The response
    """
    try:
        return Result.succ(
            service.get_list_by_page(
                {},
                page,
                page_size,
            )
        )

    except Exception as e:
        logger.exception("查询评测记录异常！")
        return Result.failed(msg=str(e), err_code="E0205")


@router.get("/evaluation/detail/show")
async def show_evaluation_detail(
    evaluate_code: Optional[str] = Query(default=None, description="evaluate code"),
    service: Service = Depends(get_service),
) -> Result:
    """Show evaluation result detail

    Args:
        evaluate_code(str): The evaluation code
        service (Service): The service
    Returns:
        ServerResponse: The response
    """

    logger.info(f"show_evaluation_detail:{evaluate_code}")
    try:
        return Result.succ(await service.get_evaluation_dicts(evaluate_code))

    except Exception as e:
        logger.exception(f"show_evaluation_detail exception:{evaluate_code}")
        return Result.failed(msg=str(e), err_code="E0213")


@router.get("/evaluation/result/download")
async def download_evaluation_result(
    evaluate_code: Optional[str] = Query(default=None, description="evaluate code"),
    service: Service = Depends(get_service),
):
    logger.info(f"download_evaluation_result:{evaluate_code}")
    try:
        file_name, stream = await service.get_evaluation_file_stream(evaluate_code)

        from urllib.parse import quote

        encoded_filename = quote(file_name)

        headers = {
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"
        }

        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except Exception as e:
        return Result.failed(msg=str(e), err_code="E0213")


@router.delete("/evaluation", response_model=Result[bool])
async def delete_evaluation(
    evaluation_code: str,
    service: Service = Depends(get_service),
) -> Result:
    """Create a new Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """

    request = EvaluateServeRequest(
        evaluate_code=evaluation_code,
    )
    return Result.succ(service.delete(request))


@router.get("/datasets", response_model=Result[PaginationResult[DatasetServeResponse]])
async def list_datasets(
    filter_param: Optional[str] = Query(default=None, description="filter param"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=100, description="page size"),
    service: DatasetService = Depends(get_dataset_service),
) -> Result[PaginationResult[DatasetServeResponse]]:
    """
    query evaluations
    Args:
        filter_param (str): The query filter param
        page (int): The page index
        page_size (int): The page size
    Returns:
        ServerResponse: The response
    """
    try:
        return Result.succ(
            service.get_list_by_page(
                {},
                page,
                page_size,
            )
        )

    except Exception as e:
        logger.exception("查询评测数据集列表异常！")
        return Result.failed(msg=str(e), err_code="E0211")


@router.post(
    "/dataset/upload/content",
    response_model=Result,
)
async def upload_dataset(
    dataset_name: str = Form(...),
    members: str = Form(...),
    content: str = Form(...),
    service: DatasetService = Depends(get_dataset_service),
) -> Result:
    try:
        return Result.succ(
            await service.upload_content_dataset(content, dataset_name, members)
        )
    except Exception as e:
        logger.exception(str(e))
        return Result.failed(msg=str(e), err_code="E0202")


@router.post(
    "/dataset/upload/file",
    response_model=Result,
)
async def upload_dataset(
    dataset_name: str = Form(...),
    members: str = Form(...),
    doc_file: UploadFile = File(...),
    service: DatasetService = Depends(get_dataset_service),
) -> Result:
    """Upload the evaluate dataset

    Args:
        doc_file (doc_file): The dataset file
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    try:
        return Result.succ(
            await service.upload_file_dataset(doc_file, dataset_name, members)
        )
    except Exception as e:
        logger.exception(str(e))
        return Result.failed(msg=str(e), err_code="E0201")


@router.get("/dataset/download")
async def download_dataset(
    code: Optional[str] = Query(default=None, description="evaluate code"),
    service: DatasetService = Depends(get_dataset_service),
) -> Result:
    """Download the evaluate dataset

    Args:
        code (str): The dataset code
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    try:
        file_name, stream = await service.get_dataset_stream(code)

        from urllib.parse import quote

        encoded_filename = quote(file_name)  # 使用 URL 编码

        headers = {
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"
        }

        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except Exception as e:
        return Result.failed(msg=str(e), err_code="E0203")


@router.delete("/dataset")
async def delete_dataset(
    code: Optional[str] = Query(default=None, description="evaluate code"),
    service: DatasetService = Depends(get_dataset_service),
) -> Result:
    """Create a new Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """

    try:

        return Result.succ(service.delete(DatasetServeRequest(code=code)))
    except Exception as e:
        return Result.failed(msg=str(e), err_code="E0204")


@router.post("/dataset/members/update")
async def update_members(
    request: DatasetServeRequest,
    service: DatasetService = Depends(get_dataset_service),
) -> Result:
    """Create a new Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """

    return Result.succ(service.update_members(request.code, request.members))


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(DatasetService)
    system_app.register(Service)
    global_system_app = system_app
