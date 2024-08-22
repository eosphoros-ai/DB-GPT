import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import StreamingResponse

from dbgpt.component import SystemApp
from dbgpt.serve.core import Result
from dbgpt.util import PaginationResult

from ..config import APP_NAME, SERVE_APP_NAME, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import (
    PromptDebugInput,
    PromptType,
    PromptVerifyInput,
    ServeRequest,
    ServerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None


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
    request: Request = None,
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
    if request.url.path.startswith(f"/api/v1"):
        return None


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


# TODO: Compatible with old API, will be modified in the future
@router.post(
    "/add", response_model=Result[ServerResponse], dependencies=[Depends(check_api_key)]
)
async def create(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Create a new Prompt entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.create(request))


@router.post(
    "/update",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def update(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Update a Prompt entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    try:
        data = service.update(request)
        return Result.succ(data)
    except Exception as e:
        logger.exception("Update prompt failed!")
        return Result.failed(msg=str(e))


@router.post(
    "/delete", response_model=Result[None], dependencies=[Depends(check_api_key)]
)
async def delete(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[None]:
    """Delete a Prompt entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.delete(request))


@router.post(
    "/list",
    response_model=Result[List[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[List[ServerResponse]]:
    """Query Prompt entities

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        List[ServerResponse]: The response
    """
    return Result.succ(service.get_list(request))


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
    """Query Prompt entities

    Args:
        request (ServeRequest): The request
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get_list_by_page(request, page, page_size))


@router.get(
    "/type/targets",
    response_model=Result,
    dependencies=[Depends(check_api_key)],
)
async def prompt_type_targets(
    prompt_type: str = Query(
        default=PromptType.NORMAL, description="Prompt template type"
    ),
    service: Service = Depends(get_service),
) -> Result:
    """get Prompt type
    Args:
        request (ServeRequest): The request

    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get_type_targets(prompt_type))


@router.post(
    "/template/load",
    response_model=Result,
    dependencies=[Depends(check_api_key)],
)
async def load_template(
    prompt_type: str = Query(
        default=PromptType.NORMAL, description="Prompt template type"
    ),
    target: Optional[str] = Query(
        default=None, description="The target to load the template from"
    ),
    service: Service = Depends(get_service),
) -> Result:
    """load Prompt from target

    Args:
        request (ServeRequest): The request

    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.load_template(prompt_type, target))


@router.post(
    "/template/debug",
    dependencies=[Depends(check_api_key)],
)
async def template_debug(
    debug_input: PromptDebugInput,
    service: Service = Depends(get_service),
):
    """test Prompt

    Args:
        request (ServeRequest): The request

    Returns:
        ServerResponse: The response
    """
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    try:
        return StreamingResponse(
            service.debug_prompt(
                debug_input=debug_input,
            ),
            headers=headers,
            media_type="text/event-stream",
        )
    except Exception as e:
        return Result.failed(msg=str(e))


@router.post(
    "/response/verify",
    response_model=Result[bool],
    dependencies=[Depends(check_api_key)],
)
async def response_verify(
    request: PromptVerifyInput,
    service: Service = Depends(get_service),
) -> Result[bool]:
    """test Prompt

    Args:
        request (ServeRequest): The request

    Returns:
        ServerResponse: The response
    """
    try:
        return Result.succ(
            service.verify_response(
                request.llm_out, request.prompt_type, request.chat_scene
            )
        )
    except Exception as e:
        return Result.failed(msg=str(e))


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service)
    global_system_app = system_app
