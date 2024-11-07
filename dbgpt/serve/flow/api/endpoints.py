import io
import json
from functools import cache
from typing import Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse, StreamingResponse

from dbgpt.component import SystemApp
from dbgpt.core.awel.flow import ResourceMetadata, ViewMetadata
from dbgpt.core.awel.flow.flow_factory import FlowCategory
from dbgpt.serve.core import Result, blocking_func_to_async
from dbgpt.util import PaginationResult

from ..config import APP_NAME, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service, _parse_flow_template_from_json
from ..service.variables_service import VariablesService
from .schemas import (
    FlowDebugRequest,
    FlowInfo,
    RefreshNodeRequest,
    ServeRequest,
    ServerResponse,
    VariablesKeyResponse,
    VariablesRequest,
    VariablesResponse,
)

router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None


def get_service() -> Service:
    """Get the service instance"""
    return Service.get_instance(global_system_app)


def get_variable_service() -> VariablesService:
    """Get the service instance"""
    return VariablesService.get_instance(global_system_app)


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
    "/flows",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
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
    res = await blocking_func_to_async(
        global_system_app, service.create_and_save_dag, request
    )
    return Result.succ(res)


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
    try:
        res = await blocking_func_to_async(
            global_system_app, service.update_flow, request
        )
        return Result.succ(res)
    except Exception as e:
        return Result.failed(msg=str(e))


@router.delete("/flows/{uid}")
async def delete(
    uid: str, service: Service = Depends(get_service)
) -> Result[ServerResponse]:
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
async def get_flows(uid: str, service: Service = Depends(get_service)):
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
    return Result.succ(flow.model_dump())


@router.get(
    "/chat/flows",
    response_model=Result[PaginationResult[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query_chat_flows(
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    name: Optional[str] = Query(default=None, description="flow name"),
    uid: Optional[str] = Query(default=None, description="flow uid"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    return Result.succ(
        service.get_list_by_page(
            {
                "user_name": user_name,
                "sys_code": sys_code,
                "name": name,
                "uid": uid,
                "flow_category": [FlowCategory.CHAT_AGENT, FlowCategory.CHAT_FLOW],
            },
            page,
            page_size,
        )
    )


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
    name: Optional[str] = Query(default=None, description="flow name"),
    uid: Optional[str] = Query(default=None, description="flow uid"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query Flow entities

    Args:
        user_name (Optional[str]): The username
        sys_code (Optional[str]): The system code
        page (int): The page number
        page_size (int): The page size
        name (Optional[str]): The flow name
        uid (Optional[str]): The flow uid
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    return Result.succ(
        service.get_list_by_page(
            {"user_name": user_name, "sys_code": sys_code, "name": name, "uid": uid},
            page,
            page_size,
        )
    )


@router.get("/nodes", dependencies=[Depends(check_api_key)])
async def get_nodes(
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    tags: Optional[str] = Query(default=None, description="tags"),
):
    """Get the operator or resource nodes

    Args:
        user_name (Optional[str]): The username
        sys_code (Optional[str]): The system code
        tags (Optional[str]): The tags encoded in JSON format

    Returns:
        Result[List[Union[ViewMetadata, ResourceMetadata]]]:
            The operator or resource nodes
    """
    from dbgpt.core.awel.flow.base import _OPERATOR_REGISTRY

    tags_dict: Optional[Dict[str, str]] = None
    if tags:
        try:
            tags_dict = json.loads(tags)
        except json.JSONDecodeError:
            return Result.fail("Invalid JSON format for tags")

    metadata_list = await blocking_func_to_async(
        global_system_app,
        _OPERATOR_REGISTRY.metadata_list,
        tags_dict,
        user_name,
        sys_code,
    )
    return Result.succ(metadata_list)


@router.post("/nodes/refresh", dependencies=[Depends(check_api_key)])
async def refresh_nodes(refresh_request: RefreshNodeRequest):
    """Refresh the operator or resource nodes

    Returns:
        Result[None]: The response
    """
    from dbgpt.core.awel.flow.base import _OPERATOR_REGISTRY

    # Make sure the variables provider is initialized
    _ = get_variable_service().variables_provider

    new_metadata = await _OPERATOR_REGISTRY.refresh(
        refresh_request.id,
        refresh_request.flow_type == "operator",
        refresh_request.refresh,
        "http",
        global_system_app,
    )
    return Result.succ(new_metadata)


@router.post(
    "/variables",
    response_model=Result[VariablesResponse],
    dependencies=[Depends(check_api_key)],
)
async def create_variables(
    variables_request: VariablesRequest,
) -> Result[VariablesResponse]:
    """Create a new Variables entity

    Args:
        variables_request (VariablesRequest): The request
    Returns:
        VariablesResponse: The response
    """
    res = await blocking_func_to_async(
        global_system_app, get_variable_service().create, variables_request
    )
    return Result.succ(res)


@router.put(
    "/variables/{v_id}",
    response_model=Result[VariablesResponse],
    dependencies=[Depends(check_api_key)],
)
async def update_variables(
    v_id: int, variables_request: VariablesRequest
) -> Result[VariablesResponse]:
    """Update a Variables entity

    Args:
        v_id (int): The variable id
        variables_request (VariablesRequest): The request
    Returns:
        VariablesResponse: The response
    """
    res = await blocking_func_to_async(
        global_system_app, get_variable_service().update, v_id, variables_request
    )
    return Result.succ(res)


@router.get(
    "/variables",
    response_model=Result[PaginationResult[VariablesResponse]],
    dependencies=[Depends(check_api_key)],
)
async def get_variables_by_keys(
    key: str = Query(..., description="variable key"),
    scope: Optional[str] = Query(default=None, description="scope"),
    scope_key: Optional[str] = Query(default=None, description="scope key"),
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
) -> Result[PaginationResult[VariablesResponse]]:
    """Get the variables by keys

    Returns:
        VariablesResponse: The response
    """
    res = await get_variable_service().get_list_by_page(
        key,
        scope,
        scope_key,
        user_name,
        sys_code,
        page,
        page_size,
    )
    return Result.succ(res)


@router.get(
    "/variables/keys",
    response_model=Result[List[VariablesKeyResponse]],
    dependencies=[Depends(check_api_key)],
)
async def get_variables_keys(
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    category: Optional[str] = Query(default=None, description="category"),
) -> Result[List[VariablesKeyResponse]]:
    """Get the variable keys

    Returns:
        VariablesKeyResponse: The response
    """
    res = await blocking_func_to_async(
        global_system_app,
        get_variable_service().list_keys,
        user_name,
        sys_code,
        category,
    )
    return Result.succ(res)


@router.post("/flow/debug", dependencies=[Depends(check_api_key)])
async def debug_flow(
    flow_debug_request: FlowDebugRequest, service: Service = Depends(get_service)
):
    """Run the flow in debug mode."""
    # Return the no-incremental stream by default
    stream_iter = service.debug_flow(flow_debug_request, default_incremental=False)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    return StreamingResponse(
        service._wrapper_chat_stream_flow_str(stream_iter),
        headers=headers,
        media_type="text/event-stream",
    )


@router.get("/flow/export/{uid}", dependencies=[Depends(check_api_key)])
async def export_flow(
    uid: str,
    export_type: Literal["json", "dbgpts"] = Query(
        "json", description="export type(json or dbgpts)"
    ),
    format: Literal["file", "json"] = Query(
        "file", description="response format(file or json)"
    ),
    file_name: Optional[str] = Query(default=None, description="file name to export"),
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    service: Service = Depends(get_service),
):
    """Export the flow to a file."""
    flow = service.get({"uid": uid, "user_name": user_name, "sys_code": sys_code})
    if not flow:
        raise HTTPException(status_code=404, detail=f"Flow {uid} not found")
    package_name = flow.name.replace("_", "-")
    file_name = file_name or package_name
    if export_type == "json":
        flow_dict = {"flow": flow.to_dict()}
        if format == "json":
            return JSONResponse(content=flow_dict)
        else:
            # Return the json file
            return StreamingResponse(
                io.BytesIO(json.dumps(flow_dict, ensure_ascii=False).encode("utf-8")),
                media_type="application/file",
                headers={
                    "Content-Disposition": f"attachment;filename={file_name}.json"
                },
            )

    elif export_type == "dbgpts":
        from ..service.share_utils import _generate_dbgpts_zip

        if format == "json":
            raise HTTPException(
                status_code=400, detail="json response is not supported for dbgpts"
            )

        zip_buffer = await blocking_func_to_async(
            global_system_app, _generate_dbgpts_zip, package_name, flow
        )
        return StreamingResponse(
            zip_buffer,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment;filename={file_name}.zip"},
        )


@router.post(
    "/flow/import",
    response_model=Result[ServerResponse],
    dependencies=[Depends(check_api_key)],
)
async def import_flow(
    file: UploadFile = File(...),
    save_flow: bool = Query(
        False, description="Whether to save the flow after importing"
    ),
    service: Service = Depends(get_service),
):
    """Import the flow from a file."""
    filename = file.filename
    file_extension = filename.split(".")[-1].lower()
    if file_extension == "json":
        # Handle json file
        json_content = await file.read()
        json_dict = json.loads(json_content)
        if "flow" not in json_dict:
            raise HTTPException(
                status_code=400, detail="invalid json file, missing 'flow' key"
            )
        flow = _parse_flow_template_from_json(json_dict)
    elif file_extension == "zip":
        from ..service.share_utils import _parse_flow_from_zip_file

        # Handle zip file
        flow = await _parse_flow_from_zip_file(file, global_system_app)
    else:
        raise HTTPException(
            status_code=400, detail=f"invalid file extension {file_extension}"
        )
    if save_flow:
        res = await blocking_func_to_async(
            global_system_app, service.create_and_save_dag, flow
        )
        return Result.succ(res)
    else:
        return Result.succ(flow)


@router.get(
    "/flow/templates",
    response_model=Result[PaginationResult[ServerResponse]],
    dependencies=[Depends(check_api_key)],
)
async def query_flow_templates(
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
) -> Result[PaginationResult[ServerResponse]]:
    """Query Flow templates."""

    res = await blocking_func_to_async(
        global_system_app,
        service.get_flow_templates,
        user_name,
        sys_code,
        page,
        page_size,
    )
    return Result.succ(res)


@router.get(
    "/flow/notebook/file/path",
    response_model=Result[FlowInfo],
    dependencies=[Depends(check_api_key)],
)
async def flow_file_path(
    flow_uid: str,
    service: Service = Depends(get_service),
) -> Result[FlowInfo]:
    try:
        return Result.succ(await service.get_flow_files(flow_uid))
    except Exception as e:
        return Result.failed(f"获取Flow文件异常！{str(e)}")


# @router.get(
#     "/flow/notebook/file/read",
#     response_model=Result[PaginationResult[ServerResponse]],
#     dependencies=[Depends(check_api_key)],
# )
# async def read_flow_python_file(
#         user_name: Optional[str] = Query(default=None, description="user name"),
#         sys_code: Optional[str] = Query(default=None, description="system code"),
#         page: int = Query(default=1, description="current page"),
#         page_size: int = Query(default=20, description="page size"),
#         service: Service = Depends(get_service),
# ) -> Result[PaginationResult[ServerResponse]]:
#
#
# @router.get(
#     "/flow/notebook/file/write",
#     response_model=Result[PaginationResult[ServerResponse]],
#     dependencies=[Depends(check_api_key)],
# )
# async def write_flow_python_file(
#         user_name: Optional[str] = Query(default=None, description="user name"),
#         sys_code: Optional[str] = Query(default=None, description="system code"),
#         page: int = Query(default=1, description="current page"),
#         page_size: int = Query(default=20, description="page size"),
#         service: Service = Depends(get_service),
# ) -> Result[PaginationResult[ServerResponse]]:


def init_endpoints(system_app: SystemApp) -> None:
    """Initialize the endpoints"""
    from .variables_provider import (
        BuiltinAgentsVariablesProvider,
        BuiltinAllSecretVariablesProvider,
        BuiltinAllVariablesProvider,
        BuiltinDatasourceVariablesProvider,
        BuiltinEmbeddingsVariablesProvider,
        BuiltinFlowVariablesProvider,
        BuiltinKnowledgeSpacesVariablesProvider,
        BuiltinLLMVariablesProvider,
        BuiltinNodeVariablesProvider,
    )

    global global_system_app
    system_app.register(Service)
    system_app.register(VariablesService)
    system_app.register(BuiltinFlowVariablesProvider)
    system_app.register(BuiltinNodeVariablesProvider)
    system_app.register(BuiltinAllVariablesProvider)
    system_app.register(BuiltinAllSecretVariablesProvider)
    system_app.register(BuiltinLLMVariablesProvider)
    system_app.register(BuiltinEmbeddingsVariablesProvider)
    system_app.register(BuiltinDatasourceVariablesProvider)
    system_app.register(BuiltinAgentsVariablesProvider)
    system_app.register(BuiltinKnowledgeSpacesVariablesProvider)
    global_system_app = system_app
