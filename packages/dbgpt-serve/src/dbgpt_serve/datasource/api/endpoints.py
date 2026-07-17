from functools import cache
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt_serve.auth.service.access import AccessService, get_access_service
from dbgpt_serve.core import ResourceTypes, Result, blocking_func_to_async
from dbgpt_serve.datasource.api.schemas import (
    DatasourceCreateRequest,
    DatasourceQueryResponse,
    DatasourceServeRequest,
)
from dbgpt_serve.datasource.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.datasource.service.service import Service
from dbgpt_serve.utils.auth import UserRequest, require_permission

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None

_SENSITIVE_PARAMETER_MARKERS = ("password", "pwd", "secret", "token", "api_key")


def _sanitize_parameters(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_parameters(item)
            for key, item in value.items()
            if not any(
                marker in str(key).lower() for marker in _SENSITIVE_PARAMETER_MARKERS
            )
        }
    if isinstance(value, list):
        return [_sanitize_parameters(item) for item in value]
    return value


def _sanitize_response(response: DatasourceQueryResponse) -> DatasourceQueryResponse:
    return response.model_copy(update={"params": _sanitize_parameters(response.params)})


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


@router.get("/health", dependencies=[Depends(check_api_key)])
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.post(
    "/datasources",
    response_model=Result[DatasourceQueryResponse],
)
async def create(
    request: Union[DatasourceCreateRequest, DatasourceServeRequest],
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("DATASOURCE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result[DatasourceQueryResponse]:
    """Create a new Space entity

    Args:
        request (Union[DatasourceCreateRequest, DatasourceServeRequest]): The request
            to create a datasource. DatasourceServeRequest is deprecated.
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    if not request.account_set_id:
        raise HTTPException(status_code=422, detail="account_set_id is required")
    access.require_account_access(operator, request.account_set_id, "DATASOURCE_MANAGE")
    res = await blocking_func_to_async(global_system_app, service.create, request)
    return Result.succ(_sanitize_response(res))


@router.put(
    "/datasources",
    response_model=Result[DatasourceQueryResponse],
)
async def update(
    request: Union[DatasourceCreateRequest, DatasourceServeRequest],
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("DATASOURCE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result[DatasourceQueryResponse]:
    """Update a Space entity

    Args:
        request (DatasourceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    if request.id is None:
        raise HTTPException(status_code=422, detail="id is required")
    resource = access.require_resource_access(
        operator, "DATASOURCE", str(request.id), manage=True
    )
    if request.account_set_id not in (None, resource.account_set_id):
        raise HTTPException(
            status_code=409,
            detail="Use the resource account-set impact and assignment APIs",
        )
    request.account_set_id = resource.account_set_id
    res = await blocking_func_to_async(global_system_app, service.update, request)
    return Result.succ(_sanitize_response(res))


@router.delete(
    "/datasources/{datasource_id}",
    response_model=Result[None],
)
async def delete(
    datasource_id: str,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("DATASOURCE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result[None]:
    """Delete a Space entity

    Args:
        request (DatasourceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    access.require_resource_access(operator, "DATASOURCE", datasource_id, manage=True)
    await blocking_func_to_async(global_system_app, service.delete, datasource_id)
    return Result.succ(None)


@router.get(
    "/datasources/{datasource_id}",
    response_model=Result[DatasourceQueryResponse],
)
async def query(
    datasource_id: str,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("DATASOURCE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result[DatasourceQueryResponse]:
    """Query Space entities

    Args:
        request (DatasourceServeRequest): The request
        service (Service): The service
    Returns:
        List[ServeResponse]: The response
    """
    access.require_resource_access(operator, "DATASOURCE", datasource_id)
    res = await blocking_func_to_async(global_system_app, service.get, datasource_id)
    return Result.succ(_sanitize_response(res))


@router.get(
    "/datasources",
    response_model=Result[List[DatasourceQueryResponse]],
)
async def query_page(
    db_type: Optional[str] = Query(
        None, description="Database type, e.g. sqlite, mysql, etc."
    ),
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("DATASOURCE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result[List[DatasourceQueryResponse]]:
    """Query Space entities

    Args:
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    res = await blocking_func_to_async(
        global_system_app, service.get_list, db_type=db_type
    )
    allowed_ids = access.allowed_resource_ids(operator, "DATASOURCE")
    if allowed_ids is not None:
        res = [item for item in res if str(item.id) in allowed_ids]
    return Result.succ([_sanitize_response(item) for item in res])


@router.get(
    "/datasource-types",
    dependencies=[Depends(require_permission("DATASOURCE_USE"))],
    response_model=Result[ResourceTypes],
)
async def get_datasource_types(
    service: Service = Depends(get_service),
) -> Result[ResourceTypes]:
    """Get the datasource types."""
    res = await blocking_func_to_async(global_system_app, service.datasource_types)
    return Result.succ(res)


@router.post(
    "/datasources/test-connection",
    dependencies=[Depends(require_permission("DATASOURCE_MANAGE"))],
    response_model=Result[bool],
)
async def test_connection(
    request: DatasourceCreateRequest, service: Service = Depends(get_service)
) -> Result[bool]:
    """Test the connection using datasource configuration before creating it

    Args:
        request (DatasourceServeRequest): The datasource configuration to test
        service (Service): The service instance

    Returns:
        Result[bool]: The test result, True if connection is successful

    Raises:
        HTTPException: When the connection test fails
    """
    res = await blocking_func_to_async(
        global_system_app, service.test_connection, request
    )
    return Result.succ(res)


@router.post(
    "/datasources/{datasource_id}/refresh",
    response_model=Result[bool],
)
async def refresh_datasource(
    datasource_id: str,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("DATASOURCE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result[bool]:
    """Refresh a datasource by its ID

    Args:
        datasource_id (str): The ID of the datasource to refresh
        service (Service): The service instance

    Returns:
        Result[bool]: The refresh result, True if the refresh was successful

    Raises:
        HTTPException: When the refresh operation fails
    """
    access.require_resource_access(operator, "DATASOURCE", datasource_id, manage=True)
    res = await blocking_func_to_async(
        global_system_app, service.refresh, datasource_id
    )
    return Result.succ(res)


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app
