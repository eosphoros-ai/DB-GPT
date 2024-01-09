import uuid
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt.serve.core import Result
from dbgpt.util import PaginationResult

from ..config import APP_NAME, SERVE_APP_NAME, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import MessageVo, ServeRequest, ServerResponse

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
    "/query",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def query(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Query Conversation entities

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.get(request))


@router.post(
    "/new",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def dialogue_new(
    chat_mode: str = "chat_normal",
    user_name: str = None,
    # TODO remove user id
    user_id: str = None,
    sys_code: str = None,
):
    user_name = user_name or user_id
    unique_id = uuid.uuid1()
    res = ServerResponse(
        user_input="",
        conv_uid=str(unique_id),
        chat_mode=chat_mode,
        user_name=user_name,
        sys_code=sys_code,
    )
    return Result.succ(res)


@router.post(
    "/delete",
    dependencies=[Depends(check_api_key)],
)
async def delete(con_uid: str, service: Service = Depends(get_service)):
    """Delete a Conversation entity

    Args:
        con_uid (str): The conversation UID
        service (Service): The service
    """
    service.delete(ServeRequest(conv_uid=con_uid))
    return Result.succ(None)


@router.post(
    "/query_page",
    response_model=Result[PaginationResult[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query_page(
    request: ServeRequest,
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=10, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query Conversation entities

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
    "/list",
    response_model=Result[List[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def list_latest_conv(
    user_name: str = None,
    user_id: str = None,
    sys_code: str = None,
    page: Optional[int] = Query(default=1, description="current page"),
    page_size: Optional[int] = Query(default=10, description="page size"),
    service: Service = Depends(get_service),
) -> Result[List[ServerResponse]]:
    """Return latest conversations"""
    request = ServeRequest(
        user_name=user_name or user_id,
        sys_code=sys_code,
    )
    return Result.succ(service.get_list_by_page(request, page, page_size).items)


@router.get(
    "/messages/history",
    response_model=Result[List[MessageVo]],
    dependencies=[Depends(check_api_key)],
)
async def get_history_messages(con_uid: str, service: Service = Depends(get_service)):
    """Get the history messages of a conversation"""
    return Result.succ(service.get_history_messages(ServeRequest(conv_uid=con_uid)))


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service)
    global_system_app = system_app
