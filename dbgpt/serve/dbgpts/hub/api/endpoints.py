import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt.serve.core import Result, blocking_func_to_async
from dbgpt.util import PaginationResult

from ..config import APP_NAME, SERVE_APP_NAME, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import ServeRequest, ServerResponse

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None

logger = logging.getLogger(__name__)


def get_service() -> Service:
    """Get the service instance"""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


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


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.post(
    "/", response_model=Result[ServerResponse], dependencies=[Depends(check_api_key)]
)
async def create(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Create a new DbgptsHub entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.create(request))


@router.put(
    "/", response_model=Result[ServerResponse], dependencies=[Depends(check_api_key)]
)
async def update(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Update a DbgptsHub entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.update(request))


@router.post(
    "/query",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def query(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Query DbgptsHub entities

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get(request))


@router.post(
    "/query_page",
    response_model=Result[PaginationResult[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query_page(
    request: ServeRequest,
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query DbgptsHub entities

    Args:
        request (ServeRequest): The request
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    try:
        return Result.succ(service.get_list_by_page(request, page, page_size))
    except Exception as e:
        logger.exception("query_page exception!")
        return Result.failed(msg=str(e))


@router.post("/source/refresh", response_model=Result[str])
async def source_refresh(
    service: Service = Depends(get_service),
):
    logger.info(f"source_refresh")
    try:
        await blocking_func_to_async(
            global_system_app,
            service.refresh_hub_from_git,
        )

        return Result.succ(None)
    except Exception as e:
        logger.error("Dbgpts hub source refresh Error!", e)
        return Result.failed(err_code="E0020", msg=f"Dbgpts Hub refresh Error! {e}")


@router.post("/install", response_model=Result[str])
async def install(request: ServeRequest):
    logger.info(f"dbgpts install:{request.name},{request.type}")

    try:
        from dbgpt.serve.dbgpts.my.config import (
            SERVE_SERVICE_COMPONENT_NAME as MY_GPTS_SERVICE_COMPONENT,
        )
        from dbgpt.serve.dbgpts.my.service.service import Service as MyGptsService

        mygpts_service: MyGptsService = global_system_app.get_component(
            MY_GPTS_SERVICE_COMPONENT, MyGptsService
        )

        await blocking_func_to_async(
            global_system_app,
            mygpts_service.install_gpts,
            name=request.name,
            type=request.type,
            repo=request.storage_channel,
            dbgpt_path=request.storage_url,
            user_name=None,
            sys_code=None,
        )
        return Result.succ(None)
    except Exception as e:
        logger.error("Plugin Install Error!", e)
        return Result.failed(err_code="E0021", msg=f"Plugin Install Error {e}")


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service)
    global_system_app = system_app
