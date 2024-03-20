from functools import cache
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt.core.awel.flow import ResourceMetadata, ViewMetadata
from dbgpt.serve.core import Result
from dbgpt.util import PaginationResult

from ..config import APP_NAME, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import ServeRequest, ServerResponse

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

    # for api_version in serve.serve_versions():
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
    "/flows", response_model=Result[None], dependencies=[Depends(check_api_key)]
)
async def create(
    request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Create a new Flow entity

    Args:
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.create_and_save_dag(request))


@router.put(
    "/flows/{uid}",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def update(
    uid: str, request: ServeRequest, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Update a Flow entity

    Args:
        uid (str): The uid
        request (ServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(service.update_flow(request))


@router.delete("/flows/{uid}")
async def delete(uid: str, service: Service = Depends(get_service)) -> Result[None]:
    """Delete a Flow entity

    Args:
        uid (str): The uid
        service (Service): The service
    Returns:
        Result[None]: The response
    """
    inst = service.delete(uid)
    return Result.succ(inst)


@router.get("/flows/{uid}")
async def get_flows(
    uid: str, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
    """Get a Flow entity by uid

    Args:
        uid (str): The uid
        service (Service): The service

    Returns:
        Result[ServerResponse]: The response
    """
    flow = service.get({"uid": uid})
    if not flow:
        raise HTTPException(status_code=404, detail=f"Flow {uid} not found")
    return Result.succ(flow)


@router.get(
    "/flows",
    response_model=Result[PaginationResult[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query_page(
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query Flow entities

    Args:
        user_name (Optional[str]): The username
        sys_code (Optional[str]): The system code
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(
        service.get_list_by_page(
            {"user_name": user_name, "sys_code": sys_code}, page, page_size
        )
    )


@router.get("/nodes", dependencies=[Depends(check_api_key)])
async def get_nodes() -> Result[List[Union[ViewMetadata, ResourceMetadata]]]:
    """Get the operator or resource nodes

    Returns:
        Result[List[Union[ViewMetadata, ResourceMetadata]]]:
            The operator or resource nodes
    """
    from dbgpt.core.awel.flow.base import _OPERATOR_REGISTRY

    return Result.succ(_OPERATOR_REGISTRY.metadata_list())


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service)
    global_system_app = system_app
