from functools import cache
from typing import List, Optional, Union

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt.util import PaginationResult
from dbgpt_ext.rag.chunk_manager import ChunkParameters
from dbgpt_serve.auth.service.access import AccessService, get_access_service
from dbgpt_serve.core import Result, blocking_func_to_async
from dbgpt_serve.rag.api.schemas import (
    DocumentServeRequest,
    DocumentServeResponse,
    KnowledgeRetrieveRequest,
    KnowledgeSyncRequest,
    SpaceServeRequest,
    SpaceServeResponse,
)
from dbgpt_serve.rag.config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from dbgpt_serve.rag.service.service import Service
from dbgpt_serve.utils.auth import UserRequest, require_permission

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


@router.get("/health", dependencies=[Depends(check_api_key)])
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.post("/spaces")
async def create(
    request: SpaceServeRequest,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Create a new Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    if not request.account_set_id:
        raise HTTPException(status_code=422, detail="account_set_id is required")
    access.require_account_access(
        operator, request.account_set_id, "KNOWLEDGE_BASE_MANAGE"
    )
    return Result.succ(service.create_space(request))


@router.put("/spaces")
async def update(
    request: SpaceServeRequest,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Update a Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    if request.id is None:
        raise HTTPException(status_code=422, detail="id is required")
    resource = access.require_resource_access(
        operator, "KNOWLEDGE_BASE", str(request.id), manage=True
    )
    if request.account_set_id not in (None, resource.account_set_id):
        raise HTTPException(
            status_code=409,
            detail="Use the resource account-set impact and assignment APIs",
        )
    request.account_set_id = resource.account_set_id
    return Result.succ(service.update_space(request))


@router.delete(
    "/spaces/{space_id}",
    response_model=Result[None],
)
async def delete(
    space_id: str,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result[None]:
    """Delete a Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    access.require_resource_access(operator, "KNOWLEDGE_BASE", space_id, manage=True)
    # TODO: Delete the files in the space
    res = await blocking_func_to_async(global_system_app, service.delete, space_id)
    return Result.succ(res)


@router.get(
    "/spaces/{space_id}",
    response_model=Result[List],
)
async def query_space(
    space_id: str,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result[List[SpaceServeResponse]]:
    """Query Space entities

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        List[ServeResponse]: The response
    """
    access.require_resource_access(operator, "KNOWLEDGE_BASE", space_id)
    request = {"id": space_id}
    return Result.succ(service.get(request))


@router.get(
    "/spaces",
    response_model=Result[PaginationResult[SpaceServeResponse]],
)
async def query_space_page(
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result[PaginationResult[SpaceServeResponse]]:
    """Query Space entities

    Args:
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    result = service.get_list_by_page({}, page, page_size)
    allowed_ids = access.allowed_resource_ids(operator, "KNOWLEDGE_BASE")
    if allowed_ids is not None:
        result.items = [item for item in result.items if str(item.id) in allowed_ids]
        result.total_count = len(result.items)
        result.total_pages = 1 if result.items else 0
    return Result.succ(result)


@router.post("/spaces/{space_id}/retrieve")
async def space_retrieve(
    space_id: int,
    request: KnowledgeRetrieveRequest,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Create a new Document entity

    Args:
        space_id (int): The space id
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    access.require_resource_access(operator, "KNOWLEDGE_BASE", str(space_id))
    request.space_id = space_id
    space_request = {
        "id": space_id,
    }
    space = service.get(space_request)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return Result.succ(await service.retrieve(request, space))


@router.post("/documents")
async def create_document(
    doc_name: str = Form(...),
    doc_type: str = Form(...),
    space_id: str = Form(...),
    content: Optional[str] = Form(None),
    doc_file: Union[UploadFile, str] = Form(None),
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    access.require_resource_access(operator, "KNOWLEDGE_BASE", space_id, manage=True)
    request = DocumentServeRequest(
        doc_name=doc_name,
        doc_type=doc_type,
        content=content,
        doc_file=doc_file,
        space_id=space_id,
    )
    res = await blocking_func_to_async(
        global_system_app, service.create_document, request
    )
    return Result.succ(res)


@router.get(
    "/documents/{document_id}",
    response_model=Result[List],
)
async def query_document(
    document_id: int,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result[List[SpaceServeResponse]]:
    """Query Space entities

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        List[ServeResponse]: The response
    """
    access.require_document_access(operator, str(document_id))
    request = {"id": document_id}
    return Result.succ(service.get_document(request))


@router.get(
    "/documents",
    response_model=Result[PaginationResult[SpaceServeResponse]],
)
async def query_document_page(
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_USE")),
    access: AccessService = Depends(get_access_service),
) -> Result[PaginationResult[DocumentServeResponse]]:
    """Query Space entities

    Args:
        page (int): The page number
        page_size (int): The page size
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    result = service.get_document_list_page({}, page, page_size)
    allowed_names = access.allowed_resource_names(operator, "KNOWLEDGE_BASE")
    if allowed_names is not None:
        result.items = [item for item in result.items if item.space in allowed_names]
        result.total_count = len(result.items)
        result.total_pages = 1 if result.items else 0
    return Result.succ(result)


@router.post("/documents/chunks/add")
async def add_documents_chunks(
    doc_name: str = Form(...),
    space_id: int = Form(...),
    content: List[str] = Form(None),
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """ """
    access.require_resource_access(
        operator, "KNOWLEDGE_BASE", str(space_id), manage=True
    )


@router.post("/documents/sync")
async def sync_documents(
    requests: List[KnowledgeSyncRequest],
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    for request in requests:
        if request.doc_id is not None:
            access.require_document_access(operator, str(request.doc_id), manage=True)
        elif request.space_id:
            access.require_resource_access(
                operator, "KNOWLEDGE_BASE", str(request.space_id), manage=True
            )
        else:
            raise HTTPException(
                status_code=422, detail="doc_id or space_id is required"
            )
    return Result.succ(service.sync_document(requests))


@router.post("/documents/batch_sync")
async def batch_sync_documents(
    requests: List[KnowledgeSyncRequest],
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    for request in requests:
        if request.doc_id is not None:
            access.require_document_access(operator, str(request.doc_id), manage=True)
        elif request.space_id:
            access.require_resource_access(
                operator, "KNOWLEDGE_BASE", str(request.space_id), manage=True
            )
        else:
            raise HTTPException(
                status_code=422, detail="doc_id or space_id is required"
            )
    return Result.succ(service.sync_document(requests))


@router.post("/documents/{document_id}/sync")
async def sync_document(
    document_id: int,
    request: KnowledgeSyncRequest,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result:
    """Create a new Document entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    access.require_document_access(operator, str(document_id), manage=True)
    request.doc_id = document_id
    if request.chunk_parameters is None:
        request.chunk_parameters = ChunkParameters(chunk_strategy="Automatic")
    return Result.succ(service.sync_document([request]))


@router.delete(
    "/documents/{document_id}",
    response_model=Result[None],
)
async def delete_document(
    document_id: str,
    service: Service = Depends(get_service),
    operator: UserRequest = Depends(require_permission("KNOWLEDGE_BASE_MANAGE")),
    access: AccessService = Depends(get_access_service),
) -> Result[None]:
    """Delete a Space entity

    Args:
        request (SpaceServeRequest): The request
        service (Service): The service
    Returns:
        ServerResponse: The response
    """
    access.require_document_access(operator, document_id, manage=True)
    # TODO: Delete the files of the document
    res = await blocking_func_to_async(
        global_system_app, service.delete_document, document_id
    )
    return Result.succ(res)


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app
